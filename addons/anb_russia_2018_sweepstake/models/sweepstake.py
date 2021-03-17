# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import Warning
from datetime import datetime
from bisect import bisect

import logging
_logger = logging.getLogger(__name__)


class RWCPlayer(models.Model):
    _name = 'rwc.player'
    _order = 'name, score_stored desc'

    @api.multi
    @api.depends('bet_ids', 'bet_ids.hit')
    def _compute_hits(self):
        for player in self:
            player.hits = len(player.bet_ids.filtered(
                lambda r: r.hit is True))

    @api.multi
    @api.depends('bet_ids', 'bet_ids.full_hit')
    def _compute_full_hits(self):
        for player in self:
            player.full_hits = len(player.bet_ids.filtered(
                lambda r: r.full_hit is True))

    @api.multi
    @api.depends('full_hits', 'hits')
    def _compute_score(self):
        for player in self:
            player.score = (
                player.full_hits * 25 + (player.hits - player.full_hits) * 8)

    @api.multi
    @api.depends('score')
    def _compute_pos(self):
        all_players = self.env['rwc.player'].search([])
        all_players_score = all_players.mapped('score')
        scores_inv = [-score for score in all_players_score]
        scores = sorted(list(set(scores_inv)))
        for player in self:
            player.pos = bisect(scores, -player.score)

    pos = fields.Integer(
        compute='_compute_pos',
        string='Position',
    )
    name = fields.Char(
        string='Alias',
        required=True,
    )
    avatar = fields.Binary(
        string='Avatar',
        attachment=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        ondelete='set null',
    )
    bet_ids = fields.One2many(
        comodel_name='rwc.bet',
        inverse_name='player_id',
        string='Bets',
    )
    hits = fields.Integer(
        compute='_compute_hits',
        string='Hits',
    )
    full_hits = fields.Integer(
        compute='_compute_full_hits',
        string='Full hits',
    )
    score = fields.Integer(
        compute='_compute_score',
        string='Score',
    )
    score_stored = fields.Integer(
        string='Score',
        readonly=True,
    )

    _sql_constraints = [
        ('user_uniq', 'unique(user_id)',
         _('A user cannot have more than one participant.')),
    ]    


class RWCBet(models.Model):
    _name = 'rwc.bet'
    _order = 'date desc'

    @api.multi
    def name_get(self):
        result = []
        for bet in self:
            result.append((bet.id, bet.display_name))
        return result

    @api.multi
    @api.depends('player_id', 'player_id.name', 'match_id',
                 'match_id.team_home', 'match_id.team_home.name',
                 'match_id.team_away', 'match_id.team_away.name',
                 'score_home', 'score_away')
    def _compute_display_name(self):
        for bet in self:
            if bet.match_id and bet.player_id:
                bet.display_name = '%s: %s %s-%s %s' % (
                    bet.player_id.name,
                    bet.match_id.team_home.name,
                    bet.score_home,
                    bet.score_away,
                    bet.match_id.team_away.name,
                )

    @api.multi
    @api.depends('score_home', 'score_away')
    def _compute_quiniela(self):
        for bet in self:
            if bet.score_home > bet.score_away:
                bet.quiniela = '1'
            elif bet.score_home < bet.score_away:
                bet.quiniela = '2'
            else:
                bet.quiniela = 'x'

    @api.multi
    @api.depends('match_id', 'match_id.score_home', 'match_id.score_away',
                 'match_id.state', 'score_home', 'score_away')
    def _compute_full_hit(self):
        for bet in self:
            if bet.state == 'finished' and \
               bet.match_id.score_home == bet.score_home and \
               bet.match_id.score_away == bet.score_away:
                bet.full_hit = True

    @api.multi
    @api.depends('match_id', 'match_id.quiniela', 'quiniela')
    def _compute_hit(self):
        for bet in self:
            if bet.state == 'finished' and \
               bet.match_id.quiniela == bet.quiniela:
                bet.hit = True

    display_name = fields.Char(
        compute='_compute_display_name',
    )
    player_id = fields.Many2one(
        comodel_name='rwc.player',
        string='Player',
        ondelete='cascade',
        default=lambda self: self.env['rwc.player'].search([
            ('user_id', '=', self.env.user.id)
        ]),
        required=True,
        states={
            'finished': [('readonly', True)],
        },
    )
    match_id = fields.Many2one(
        comodel_name='rwc.match',
        domain="[('state', '!=', 'finished')]",
        string='Match',
        ondelete='cascade',
        required=True,
        states={
            'finished': [('readonly', True)],
        },
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    team_home = fields.Many2one(
        related='match_id.team_home',
        readonly=True,
    )
    team_away = fields.Many2one(
        related='match_id.team_away',
        readonly=True,
    )
    flag_home = fields.Binary(
        related='team_home.flag',
        readonly=True,
    )
    flag_away = fields.Binary(
        related='team_away.flag',
        readonly=True,
    )
    score_home = fields.Integer(
        string='Home score',
        required=True,
        default=0,
        states={
            'finished': [('readonly', True)],
        },
    )
    score_away = fields.Integer(
        string='Away score',
        required=True,
        default=0,
        states={
            'finished': [('readonly', True)],
        },
    )
    quiniela = fields.Selection(
        compute='_compute_quiniela',
        selection=[
            ('1', '1'),
            ('x', 'X'),
            ('2', '2'),
        ],
        string='Quiniela',
    )
    hit = fields.Boolean(
        compute='_compute_hit',
        string='Hit',
    )
    full_hit = fields.Boolean(
        compute='_compute_full_hit',
        string='Full hit',
    )
    state = fields.Selection(
        related='match_id.state',
        readonly=True,
    )

    _sql_constraints = [
        ('bet_uniq', 'unique(player_id, match_id)',
         _('A player cannot have more than one bet in a match.')),
    ]

    @api.one
    @api.constrains('create_date', 'match_id')
    def _check_date(self):
        create_date = fields.Datetime.from_string(self.create_date)
        date = fields.Datetime.from_string(self.match_id.date)
        if create_date > date and \
            not self.env.user.has_group(
                'anb_russia_2018_sweepstake.sweepstake_admin_group_user'):
            raise Warning(
                _('Too late to bet! Bets are forbidden after the beginning of '
                  'the match.'),
            )

    @api.multi
    def write(self, vals):
        for bet in self:
            if 'match_id' in vals or 'player_id' in vals or \
              'score_home' in vals or 'score_away' in vals:
                write_date = fields.Datetime.from_string(fields.Datetime.now())
                date = fields.Datetime.from_string(bet.match_id.date)
                if write_date > date and \
                    not self.env.user.has_group(
                        'anb_russia_2018_sweepstake.'
                        'sweepstake_admin_group_user'):
                    if ('match_id' in vals and
                       bet.match_id.id != vals.get('match_id', False)) or \
                       ('player_id' in vals and
                       bet.player_id.id != vals.get('player_id', False)) or \
                       ('score_home' in vals and
                       bet.score_home != vals.get('score_home', False)) or \
                       ('score_away' in vals and
                       bet.score_away != vals.get('score_away', False)):
                        raise Warning(
                            _('Too late to bet! Bets forbidden after the '
                              'beginning of the match.'),
                        )
        res = super(RWCBet, self).write(vals)
        for bet in self:
            bet.player_id.score_stored = bet.player_id.score
        return res


class RWCMatch(models.Model):
    _name = 'rwc.match'
    _order = 'date'

    @api.multi
    def name_get(self):
        result = []
        for match in self:
            result.append((match.id, match.display_name))
        return result

    @api.multi
    @api.depends('team_home', 'team_home.name', 'team_away', 'team_away.name',
                 'score_home', 'score_away')
    def _compute_display_name(self):
        for match in self:
            if match.team_home and match.team_away:
                if match.state == 'finished':
                    match.display_name = '%s %s-%s %s' % (
                        match.team_home.name,
                        match.score_home,
                        match.score_away,
                        match.team_away.name,
                    )
                else:
                    match.display_name = '%s - %s' % (
                        match.team_home.name,
                        match.team_away.name,
                    )

    @api.multi
    @api.depends('score_home', 'score_away')
    def _compute_quiniela(self):
        for match in self:
            if match.score_home > match.score_away:
                match.quiniela = '1'
            elif match.score_home < match.score_away:
                match.quiniela = '2'
            else:
                match.quiniela = 'x'

    @api.multi
    def set_as_finished(self):
        self.ensure_one()
        self.write({
            'state': 'finished',
        })

    @api.multi
    def set_as_to_play(self):
        self.ensure_one()
        self.write({
            'state': 'to_play',
        })

    display_name = fields.Char(
        compute='_compute_display_name',
    )
    team_home = fields.Many2one(
        comodel_name='rwc.team',
        string='Home team',
        required=True,
        ondelete='cascade',
        states={
            'finished': [('readonly', True)],
        },
    )
    team_away = fields.Many2one(
        comodel_name='rwc.team',
        string='Away team',
        required=True,
        ondelete='cascade',
        states={
            'finished': [('readonly', True)],
        },
    )
    flag_home = fields.Binary(
        related='team_home.flag',
        readonly=True,
    )
    flag_away = fields.Binary(
        related='team_away.flag',
        readonly=True,
    )
    score_home = fields.Integer(
        string='Home score',
        default=0,
        states={
            'finished': [('readonly', True)],
        },
    )
    score_away = fields.Integer(
        string='Away score',
        default=0,
        states={
            'finished': [('readonly', True)],
        },
    )
    quiniela = fields.Selection(
        compute='_compute_quiniela',
        selection=[
            ('1', '1'),
            ('x', 'X'),
            ('2', '2'),
        ],
        string='Quiniela',
    )
    date = fields.Datetime(
        string='Date',
        required=True,
        states={
            'finished': [('readonly', True)],
        },
    )
    bet_ids = fields.One2many(
        comodel_name='rwc.bet',
        inverse_name='match_id',
        string='Bets',
        states={
            'finished': [('readonly', True)],
        },
    )
    match_round = fields.Selection(
        selection=[
            ('group_phase', 'Group phase'),
            ('round_of_16', 'Round of 16'),
            ('quarter_finals', 'Quarter-finals'),
            ('semi_finals', 'Semi-finals'),
            ('third_place', 'Play-off for third place'),
            ('final', 'Final'),
        ],
        string='Round',
        required=True,
        states={
            'finished': [('readonly', True)],
        },
    )
    state = fields.Selection(
        selection=[
            ('to_play', 'To play'),
            ('finished', 'Finished'),
        ],
        string='State',
        default='to_play',
        readonly=True,
    )

    @api.multi
    def write(self, vals):
        res = super(RWCMatch, self).write(vals)
        for match in self:
            for bet in match.bet_ids:
                bet.player_id.score_stored = bet.player_id.score
        return res

    @api.multi
    def add_your_bet(self):
        self.ensure_one()
        player = self.env['rwc.player'].search([
            ('user_id', '=', self.env.user.id),
        ])
        if len(player) == 0:
            raise Warning(
                _('First, create a participant for your user. Ask the game '
                  'manager for that if you do not have permissions to create '
                  'any participants.')
            )
        player.ensure_one()
        action = self.env.ref('anb_russia_2018_sweepstake.action_rwc_open_bet')
        action_dict = action.read()[0]
        action_dict.update({
            'view_mode': 'form',
            'views': [(False, u'form')],
            'context': {
                'default_match_id': self.id,
                'default_player_id': player.id,
            }
        })
        bet = self.env['rwc.bet'].search([
            ('match_id', '=', self.id),
            ('player_id', '=', player.id),
        ])
        if bet and bet.ensure_one():
            action_dict.update({
                'res_id': bet.id,
            })
        else:
            write_date = fields.Datetime.from_string(fields.Datetime.now())
            date = fields.Datetime.from_string(self.date)
            if write_date > date and \
                not self.env.user.has_group(
                    'anb_russia_2018_sweepstake.'
                    'sweepstake_admin_group_user'):
                raise Warning(
                    _('Too late to bet! Bets are forbidden after the '
                      'beginning of the match.'),
                )
        return action_dict


class RWCTeam(models.Model):
    _name = 'rwc.team'
    _order = 'name'

    name = fields.Char(
        string='Name',
        required=True,
    )
    flag = fields.Binary(
        string='Flag',
    )
