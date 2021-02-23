# -*- coding: utf-8 -*-
#############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012-Today Serpent Consulting Services Pvt. Ltd.
#    (<http://www.serpentcs.com>)
#    Copyright (C) 2004 OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
#############################################################################

from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.exceptions import except_orm, ValidationError
from dateutil.relativedelta import relativedelta
from openerp import models, fields, api, _
import datetime
import time
import dateutil
from dateutil.parser import parse


class HotelFolio(models.Model):
    _inherit = 'hotel.folio'
    _order = 'reservation_id desc'

    reservation_id = fields.Many2one(comodel_name='hotel.reservation',
                                     string='Reservation Id')


class HotelFolioLineExt(models.Model):
    _inherit = 'hotel.folio.line'

    @api.multi
    def write(self, vals):
        """
        Overrides orm write method.
        @param self: The object pointer
        @param vals: dictionary of fields value.
        """
        # Update Hotel Room Reservation line history
        reservation_line_obj = self.env['hotel.room.reservation.line']
        room_obj = self.env['hotel.room']
        prod_id = vals.get('product_id') or self.product_id.id
        chkin = vals.get('checkin_date') or self.checkin_date
        chkout = vals.get('checkout_date') or self.checkout_date
        is_reserved = self.is_reserved

        if prod_id and is_reserved:
            prod_domain = [('product_id', '=', prod_id)]
            prod_room = room_obj.search(prod_domain, limit=1)

            if (self.product_id and self.checkin_date and self.checkout_date):
                old_prd_domain = [('product_id', '=', self.product_id.id)]
                old_prod_room = room_obj.search(old_prd_domain, limit=1)
                if prod_room and old_prod_room:
                    # check for existing room lines.
                    srch_rmline = [('room_id', '=', old_prod_room.id),
                                   ('check_in', '=', self.checkin_date),
                                   ('check_out', '=', self.checkout_date),
                                   ]
                    rm_lines = reservation_line_obj.search(srch_rmline)
                    if rm_lines:
                        rm_line_vals = {'room_id': prod_room.id,
                                        'check_in': chkin,
                                        'check_out': chkout}
                        rm_lines.write(rm_line_vals)
        return super(HotelFolioLineExt, self).write(vals)


class HotelReservation(models.Model):
    _name = "hotel.reservation"
    _rec_name = "reservation_no"
    _description = "Reservation"
    _order = 'reservation_no desc'
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    reservation_no = fields.Char('Reservation No', size=64, readonly=True)
    date_order = fields.Datetime('Date Ordered', required=True, readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 default=(lambda *a:
                                          time.strftime
                                          (DEFAULT_SERVER_DATETIME_FORMAT)))
    warehouse_id = fields.Many2one('stock.warehouse', 'Hotel', readonly=True,
                                   required=True, default=1,
                                   states={'draft': [('readonly', False)]})
    partner_id = fields.Many2one('res.partner', 'Guest Name', readonly=True,
                                 required=True,
                                 states={'draft': [('readonly', False)]})
    pricelist_id = fields.Many2one('product.pricelist', 'Scheme',
                                   required=True, readonly=True,
                                   states={'draft': [('readonly', False)]},
                                   help="Pricelist for current reservation.")
    partner_invoice_id = fields.Many2one('res.partner', 'Invoice Address',
                                         readonly=True,
                                         states={'draft':
                                                     [('readonly', False)]},
                                         help="Invoice address for "
                                              "current reservation.")
    partner_order_id = fields.Many2one('res.partner', 'Ordering Contact',
                                       readonly=True,
                                       states={'draft':
                                                   [('readonly', False)]},
                                       help="The name and address of the "
                                            "contact that requested the order "
                                            "or quotation.")
    partner_shipping_id = fields.Many2one('res.partner', 'Delivery Address',
                                          readonly=True,
                                          states={'draft':
                                                      [('readonly', False)]},
                                          help="Delivery address"
                                               "for current reservation. ")
    checkin = fields.Datetime('Expected-Date-Arrival', required=True,
                              readonly=True,
                              states={'draft': [('readonly', False)]})
    checkout = fields.Datetime('Expected-Date-Departure', required=True,
                               readonly=True,
                               states={'draft': [('readonly', False)]})
    email_checkin = fields.Date('Email Checkin')
    email_checkout = fields.Date('Email Checkout')
    adults = fields.Integer('Adults', size=64, readonly=True,
                            states={'draft': [('readonly', False)]},
                            help='List of adults there in guest list. ')
    children = fields.Integer('Children', size=64, readonly=True,
                              states={'draft': [('readonly', False)]},
                              help='Number of children there in guest list.')
    reservation_line = fields.One2many('hotel_reservation.line', 'line_id',
                                       'Reservation Line',
                                       help='Hotel room reservation details.')
    reservation_service_line = fields.One2many('hotel_reservation.service.line', 'service_line_id',
                                               'Service Line',
                                               help='Hotel Service line details.')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'),
                              ('cancel', 'Cancel'), ('done', 'Done')],
                             'State', readonly=True,
                             default=lambda *a: 'draft')
    folio_id = fields.Many2many('hotel.folio', 'hotel_folio_reservation_rel',
                                'order_id', 'invoice_id', string='Folio')
    folio_no = fields.Many2one('hotel.folio', 'Folio No', domain=[('state', '=', 'draft')])
    dummy = fields.Datetime('Dummy')
    memo = fields.Char('Memo')
    apartment = fields.Boolean('Apartment', readonly=True,
                               states={'draft': [('readonly', False)]})
    vat_tax = fields.Float('VAT Tax')
    acco_tax = fields.Float('Acco Tax')
    total = fields.Float('Total')
    sub_tot = fields.Float('Subtotal')

    @api.constrains('reservation_line','reservation_service_line','checkin','checkout')
    def _set_reservation_price(self):
        subtotal = 0
        for res in self.reservation_line:
            for room in res.reserve:
                for version in self.pricelist_id.version_id:
                    in_pricelist = False
                    for pricelist in version.items_id:
                        price = (room.list_price * (1 + pricelist.price_discount) + pricelist.price_surcharge)
                        if room.categ_id.name == pricelist.categ_id.name:
                            in_pricelist = True
                            subtotal = subtotal + price
                            break
                    if not in_pricelist:
                        subtotal = subtotal + room.list_price

        server_dt = DEFAULT_SERVER_DATETIME_FORMAT
        checkin = datetime.datetime.strptime(self.checkin, server_dt)
        checkout = datetime.datetime.strptime(self.checkout, server_dt)
        duration = checkout - checkin + datetime.timedelta(days=1)

        sub_total = subtotal * duration.days
        self.sub_tot = sub_total
        self.acco_tax = sub_total * 0.02
        self.vat_tax = sub_total * 1.02 * 0.1
        self.total = sub_total * 1.122

    @api.multi
    def _defaults_checkin_date(self):
        checkin = datetime.datetime.now().strftime("%Y-%m-%d 07:00:00")
        return checkin

    @api.multi
    def _defaults_checkout_date(self):
        checkout = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d 05:00:00")
        return checkout

    @api.onchange('folio_no')
    def _set_in_out_date(self):
        self.checkin = self.folio_no.checkin_date
        self.checkout = self.folio_no.checkout_date
        self.partner_id = self.folio_no.partner_id
        if not self.checkin or not self.checkout:
            self.checkin = self._defaults_checkin_date()
            self.checkout = self._defaults_checkout_date()

    @api.multi
    def unlink(self):
        raise ValidationError(_('Sorry! You can not delete Reservation.'))

    @api.constrains('reservation_line', 'adults', 'children')
    def check_reservation_rooms(self):
        '''
        This method is used to validate the reservation_line.
        -----------------------------------------------------
        @param self: object pointer
        @return: raise a warning depending on the validation
        '''
        for reservation in self:
            if len(reservation.reservation_line) == 0:
                raise ValidationError(_('Please Select Rooms \
                For Reservation.'))
            for rec in reservation.reservation_line:
                if len(rec.reserve) == 0:
                    raise ValidationError(_('Please Select Rooms \
                    For Reservation.'))
                cap = 0
                for room in rec.reserve:
                    cap += room.capacity
                if (self.adults + self.children) > cap:
                    raise ValidationError(_('Room Capacity \
                        Exceeded \n Please Select Rooms According to \
                        Members Accomodation.'))

    @api.constrains('checkin', 'checkout')
    def check_in_out_dates(self):
        """
        When date_order is less then checkin date or
        Checkout date should be greater than the checkin date.
        """
        if self.checkout and self.checkin:
            if self.checkin < self.date_order:
                raise except_orm(_('Warning'), _('Checkin date should be \
                greater than the current date.'))
            if self.checkout < self.checkin:
                raise except_orm(_('Warning'), _('Checkout date \
                should be greater than Checkin date.'))

    @api.model
    def _needaction_count(self, domain=None):
        """
         Show a count of draft state reservations on the menu badge.
         """
        return self.search_count([('state', '=', 'draft')])

    @api.onchange('checkout', 'checkin')
    def on_change_checkout(self):
        '''
        When you change checkout or checkin update dummy field
        -----------------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        checkout_date = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        checkin_date = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        if not (checkout_date and checkin_date):
            return {'value': {}}
        delta = datetime.timedelta(days=1)
        dat_a = time.strptime(checkout_date,
                              DEFAULT_SERVER_DATETIME_FORMAT)[:5]
        addDays = datetime.datetime(*dat_a) + delta
        self.dummy = addDays.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        '''
        When you change partner_id it will update the partner_invoice_id,
        partner_shipping_id and pricelist_id of the hotel reservation as well
        ---------------------------------------------------------------------
        @param self: object pointer
        '''
        if not self.partner_id:
            self.partner_invoice_id = False
            self.partner_shipping_id = False
            self.partner_order_id = False
        else:
            addr = self.partner_id.address_get(['delivery', 'invoice',
                                                'contact'])
            self.partner_invoice_id = addr['invoice']
            self.partner_order_id = addr['contact']
            self.partner_shipping_id = addr['delivery']
            self.pricelist_id = self.partner_id.property_product_pricelist.id

    @api.multi
    def confirmed_reservation(self):
        """
        This method create a new recordset for hotel room reservation line
        ------------------------------------------------------------------
        @param self: The object pointer
        @return: new record set for hotel room reservation line.
        """
        reservation_line_obj = self.env['hotel.room.reservation.line']
        for reservation in self:
            self._cr.execute("select count(*) from hotel_reservation as hr "
                             "inner join hotel_reservation_line as hrl on \
                             hrl.line_id = hr.id "
                             "inner join hotel_reservation_line_room_rel as \
                             hrlrr on hrlrr.room_id = hrl.id "
                             "where (checkin,checkout) overlaps \
                             ( timestamp %s, timestamp %s ) "
                             "and hr.id <> cast(%s as integer) "
                             "and hr.state = 'confirm' "
                             "and hrlrr.hotel_reservation_line_id in ("
                             "select hrlrr.hotel_reservation_line_id \
                             from hotel_reservation as hr "
                             "inner join hotel_reservation_line as \
                             hrl on hrl.line_id = hr.id "
                             "inner join hotel_reservation_line_room_rel \
                             as hrlrr on hrlrr.room_id = hrl.id "
                             "where hr.id = cast(%s as integer) )",
                             (reservation.checkin, reservation.checkout,
                              str(reservation.id), str(reservation.id)))
            res = self._cr.fetchone()
            roomcount = res and res[0] or 0.0
            if roomcount:
                raise except_orm(_('Warning'), _('You tried to confirm \
                reservation with room those already reserved in this \
                reservation period'))
            else:
                self.write({'state': 'confirm'})
                for line_id in reservation.reservation_line:
                    line_id = line_id.reserve
                    for room_id in line_id:
                        vals = {
                            'room_id': room_id.id,
                            'check_in': reservation.checkin,
                            'check_out': reservation.checkout,
                            'state': 'assigned',
                            'reservation_id': reservation.id,
                        }
                        room_id.write({'isroom': False, 'status': 'occupied'})
                        reservation_line_obj.create(vals)
        return True

    @api.multi
    def cancel_reservation(self):

        """
        This method cancel recordset for hotel room reservation line
        ------------------------------------------------------------------
        @param self: The object pointer
        @return: cancel record set for hotel room reservation line.
        """
        room_res_line_obj = self.env['hotel.room.reservation.line']
        hotel_res_line_obj = self.env['hotel_reservation.line']
        self.write({'state': 'cancel'})
        room_reservation_line = room_res_line_obj.search([('reservation_id',
                                                           'in', self.ids)])
        room_reservation_line.write({'state': 'unassigned'})
        reservation_lines = hotel_res_line_obj.search([('line_id',
                                                        'in', self.ids)])
        for reservation_line in reservation_lines:
            reservation_line.reserve.write({'isroom': True,
                                            'status': 'available'})
        return True

    @api.multi
    def set_to_draft_reservation(self):
        for reservation in self:
            reservation.write({'state': 'draft'})
        return True

    @api.multi
    def send_reservation_maill(self):
        self.email_checkin = dateutil.parser.parse(self.checkin).date()
        self.email_checkout = dateutil.parser.parse(self.checkout).date()

        assert len(self._ids) == 1, 'This is for a single id at a time.'
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = (ir_model_data.get_object_reference
            ('hotel_reservation',
             'custom_email_template_hotel_reservation')[1])
        except ValueError:
            template_id = False
        try:
            compose_form_id = (ir_model_data.get_object_reference
            ('mail',
             'email_compose_message_wizard_form')[1])
        except ValueError:
            compose_form_id = False
        ctx = dict()
        ctx.update({
            'default_model': 'hotel.reservation',
            'default_res_id': self._ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'force_send': True,
            'mark_so_as_sent': True
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
            'force_send': True
        }

    @api.model
    def reservation_reminder_24hrs(self):
        self.email_checkin = dateutil.parser.parse(self.checkin).date()
        self.email_checkout = dateutil.parser.parse(self.checkout).date()

        now_str = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        now_date = datetime.datetime.strptime(now_str,
                                              DEFAULT_SERVER_DATETIME_FORMAT)
        ir_model_data = self.env['ir.model.data']
        template_id = (ir_model_data.get_object_reference
        ('hotel_reservation',
         'email_template_reservation_reminder_24hrs_so')[1])
        template_rec = self.env['email.template'].browse(template_id)
        for travel_rec in self.search([]):
            checkin_date = (datetime.datetime.strptime
                            (travel_rec.checkin,
                             DEFAULT_SERVER_DATETIME_FORMAT))
            difference = relativedelta(now_date, checkin_date)
            if (difference.days == -1 and travel_rec.partner_id.email and
                    travel_rec.state == 'confirm'):
                template_rec.send_mail(travel_rec.id, force_send=True)
        return True

    @api.multi
    def _create_folio(self):
        hotel_folio_obj = self.env['hotel.folio']
        room_obj = self.env['hotel.room']
        product_obj = self.env['product.product']
        # PISEY KORN ADDED ##############################################################
        if self.folio_no.id:
            hsl_obj = self.env['hotel.service.line']
            hfl_obj = self.env['hotel.folio.line']

            date_a = (datetime.datetime
                      (*time.strptime(self.checkout,
                                      DEFAULT_SERVER_DATETIME_FORMAT)[:5]))
            date_b = (datetime.datetime
                      (*time.strptime(self.checkin,
                                      DEFAULT_SERVER_DATETIME_FORMAT)[:5]))

            for line in self.reservation_line:
                for r in line.reserve:
                    hfl_obj.create({
                        'tax_id': [(6, 0, [x.id for x in r.taxes_id])],
                        'folio_id': self.folio_no.id,
                        'checkin_date': self.checkin,
                        'checkout_date': self.checkout,
                        'room_no': r.id,
                        'name': r.name,
                        'product_uom': r.uos_id.id,
                        'price_unit': r.list_price,
                        'product_uom_qty': ((date_a - date_b).days) + 1,
                        'is_reserved': True,
                        'reservation_id': self.id
                    })
            for line in self.reservation_service_line:
                product_id = product_obj.search([('name', '=', line.product_id.name)])
                is_existing = False
                for s_line in self.folio_no.service_lines:
                    if product_id.id == s_line.product_id.id:
                        s_line.product_uom_qty += line.product_uom_qty
                        is_existing = True
                if not is_existing:
                    hsl_obj.create({
                        'tax_id': [(6, 0, [x.id for x in product_id.taxes_id])],
                        'folio_id': self.folio_no.id,
                        'ser_checkin_date': self.checkin,
                        'ser_checkout_date': self.checkout,
                        'product_id': product_id.id,
                        'name': line.name,
                        'product_uom': line.uom_id.id,
                        'price_unit': line.list_price,
                        'product_uom_qty': line.product_uom_qty
                    })
            self.write({'state': 'done'})
        #################################################################################
        else:
            for reservation in self:
                folio_lines = []
                res_service_lines = []
                checkin_date = reservation['checkin']
                checkout_date = reservation['checkout']
                if not self.checkin < self.checkout:
                    raise except_orm(_('Error'),
                                     _('Checkout date should be greater \
                                         than the Checkin date.'))
                duration_vals = (self.onchange_check_dates
                                 (checkin_date=checkin_date,
                                  checkout_date=checkout_date, duration=False))
                duration = duration_vals.get('duration') or 0.0
                folio_vals = {
                    'date_order': reservation.date_order,
                    'warehouse_id': reservation.warehouse_id.id,
                    'apartment': reservation.apartment,
                    'partner_id': reservation.partner_id.id,
                    'pricelist_id': reservation.pricelist_id.id,
                    'partner_invoice_id': reservation.partner_invoice_id.id,
                    'partner_shipping_id': reservation.partner_shipping_id.id,
                    'checkin_date': reservation.checkin,
                    'checkout_date': reservation.checkout,
                    'duration': duration,
                    'reservation_id': reservation.id,
                    'memo': reservation.memo,
                    'service_lines': reservation['folio_id']
                }
                date_a = (datetime.datetime
                          (*time.strptime(reservation['checkout'],
                                          DEFAULT_SERVER_DATETIME_FORMAT)[:5]))
                date_b = (datetime.datetime
                          (*time.strptime(reservation['checkin'],
                                          DEFAULT_SERVER_DATETIME_FORMAT)[:5]))
                for line in reservation.reservation_line:
                    for r in line.reserve:
                        product_uom = r.uos_id.id
                        price_unit = r.list_price
                        folio_lines.append((0, 0, {
                            'tax_id': [(6, 0, [x.id for x in r.taxes_id])],
                            'checkin_date': checkin_date,
                            'checkout_date': checkout_date,
                            'room_no': r.id,
                            'name': r.name,
                            'product_uom': product_uom,
                            'price_unit': price_unit,
                            'product_uom_qty': ((date_a - date_b).days) + 1,
                            'is_reserved': True,
                            'reservation_id': reservation.id}))
                        res_obj = room_obj.browse([r.id])
                        res_obj.write({'status': 'occupied', 'isroom': False})

                for line in reservation.reservation_service_line:
                    product_id = product_obj.search([('name', '=', line.product_id.name)])
                    product_uom = line.uom_id.id
                    price_unit = line.list_price
                    quantity = line.product_uom_qty
                    res_service_lines.append((0, 0, {
                        'tax_id': [(6, 0, [x.id for x in product_id.taxes_id])],
                        'ser_checkin_date': checkin_date,
                        'ser_checkout_date': checkout_date,
                        'product_id': product_id.id,
                        'name': line.name,
                        'product_uom': product_uom,
                        'price_unit': price_unit,
                        'product_uom_qty': quantity}))

                folio_vals.update({'room_lines': folio_lines, 'service_lines': res_service_lines})
                folio = hotel_folio_obj.create(folio_vals)
                self._cr.execute('insert into hotel_folio_reservation_rel'
                                 '(order_id, invoice_id) values (%s,%s)',
                                 (reservation.id, folio.id)
                                 )
                reservation.write({'state': 'done', 'folio_no': folio.id})

        return True

    @api.multi
    def onchange_check_dates(self, checkin_date=False, checkout_date=False,
                             duration=False):
        '''
        This mathod gives the duration between check in checkout if
        customer will leave only for some hour it would be considers
        as a whole day. If customer will checkin checkout for more or equal
        hours, which configured in company as additional hours than it would
        be consider as full days
        --------------------------------------------------------------------
        @param self: object pointer
        @return: Duration and checkout_date
        '''
        value = {}
        company_obj = self.env['res.company']
        configured_addition_hours = 0
        company_ids = company_obj.search([])
        if company_ids.ids:
            configured_addition_hours = company_ids[0].additional_hours
        duration = 0
        if checkin_date and checkout_date:
            chkin_dt = (datetime.datetime.strptime
                        (checkin_date, DEFAULT_SERVER_DATETIME_FORMAT))
            chkout_dt = (datetime.datetime.strptime
                         (checkout_date, DEFAULT_SERVER_DATETIME_FORMAT))
            dur = chkout_dt - chkin_dt
            duration = dur.days + 1
            if configured_addition_hours > 0:
                additional_hours = abs((dur.seconds / 60) / 60)
                if additional_hours >= configured_addition_hours:
                    duration += 1
        value.update({'duration': duration})
        return value

    @api.model
    def create(self, vals):
        if not vals:
            vals = {}
        if self._context is None:
            self._context = {}
        vals['reservation_no'] = self.env['ir.sequence'].get('hotel.reservation')
        return super(HotelReservation, self).create(vals)

    # PISEY KORN ADDED ####################################################
    @api.multi
    def write(self, vals):
        new_room_ids = []
        pre_room_ids = []
        addId = []
        deleteId = []
        room_reservation_line_obj = self.env['hotel.room.reservation.line']
        for lines in self.reservation_line:
            for room in lines.reserve:
                pre_room_ids.append(room.id)
        res = super(HotelReservation, self).write(vals)
        if vals.get('reservation_line'):
            for line in self.reservation_line:
                for room in line.reserve:
                    new_room_ids.append(room.id)
            for i in new_room_ids:
                if i not in pre_room_ids:
                    addId.append(i)
            for i in pre_room_ids:
                if i not in new_room_ids:
                    deleteId.append(i)
            line_ids = room_reservation_line_obj.search(
                [('reservation_id.id', '=', self.id)])
            for line in line_ids:
                if line.room_id.id in deleteId:
                    line.unlink()
            for r in addId:
                room_reservation_dic = {
                    'room_id': r,
                    'reservation_id': self.id,
                    'check_in': self.checkin,
                    'check_out': self.checkout,
                    'state': 'assigned',
                }
                room_reservation_line_obj.create(room_reservation_dic)
        return res
    #######################################################################


class HotelReservationLine(models.Model):
    _name = "hotel_reservation.line"
    _description = "Reservation Line"

    # PISEY ADDED ################
    @api.model
    def _set_categ_id(self):
        if self._context:
            self.categ_id = False
            self.categ_id_2 = False

    ##############################

    name = fields.Char('Name', size=64)
    line_id = fields.Many2one('hotel.reservation')
    reserve = fields.Many2many('hotel.room',
                               'hotel_reservation_line_room_rel',
                               'hotel_reservation_line_id', 'room_id',domain="[('categ_id','=',categ_id),('categ_id_2','=',categ_id_2)]")
    categ_id = fields.Many2one('hotel.room.type', 'Room Type', compute=_set_categ_id,domain="[('categ_id','=',True)]")
    categ_id_2 = fields.Many2one('hotel.room.type', 'Category', compute=_set_categ_id,domain="[('categ_id','=',False)]")

    @api.onchange('categ_id','categ_id_2')
    def on_change_categ(self):
        if not self.line_id.checkin:
            raise except_orm(_('Warning'),
                             _('Before choosing a room,\n You have to select \
                             a Check in date or a Check out date in \
                             the reservation form.'))
        #### PISEY ADDED ########################################################
        if self.categ_id and self.categ_id_2:
            hotel_room_obj = self.env['hotel.room']
            hotel_room_ids = hotel_room_obj.search([('categ_id', '=',
                                                     self.categ_id_2.id),('categ_id_2','=',self.categ_id.id)])
            room_ids = []
            checkIn = parse(self.line_id.checkin)
            checkOut = parse(self.line_id.checkout)
            for r in hotel_room_ids:
                available = 1
                for line in r.room_reservation_line_ids:
                    line_checkin = parse(line.check_in)
                    line_checkout = parse(line.check_out)
                    if line.status != "cancel":
                        if (checkIn >= line_checkin and checkIn <= line_checkout) or (
                                checkOut >= line_checkin and checkOut <= line_checkout) or (
                                checkIn < line_checkin and checkOut > line_checkout):
                            available = 0
                            break
                for line in r.room_line_ids:
                    line_checkin = parse(line.check_in)
                    line_checkout = parse(line.check_out)
                    if line.status != "cancel":
                        if (checkIn >= line_checkin and checkIn <= line_checkout) or (
                                checkOut >= line_checkin and checkOut <= line_checkout) or (
                                checkIn < line_checkin and checkOut > line_checkout):
                            available = 0
                            break
                if available == 1:
                    room_ids.append(r.id)
            #########################################################################
            domain = {'reserve': [('id', 'in', room_ids)]}
            return {'domain': domain}
        else:
            domain = {'reserve': [('id', 'in', [])]}
            return {'domain': domain}

    @api.multi
    def unlink(self):
        hotel_room_reserv_line_obj = self.env['hotel.room.reservation.line']
        for reserv_rec in self:
            for rec in reserv_rec.reserve:
                hres_arg = [('room_id', '=', rec.id),
                            ('reservation_id', '=', reserv_rec.line_id.id)]
                myobj = hotel_room_reserv_line_obj.search(hres_arg)
                if myobj.ids:
                    rec.write({'isroom': True, 'status': 'available'})
                    myobj.unlink()
        return super(HotelReservationLine, self).unlink()


class ReservationServiceLine(models.Model):
    _name = 'hotel_reservation.service.line'

    _description = 'Hotel Reservation Service Line'

    service_line_id = fields.Many2one('hotel.reservation')
    product_id = fields.Many2one('hotel.services', required=True)
    price_subtotal = fields.Float('Subtotal', readonly=True)
    product_uom_qty = fields.Float('Quantity', default=1, required=True)
    list_price = fields.Float('Price Unit', required=True)
    name = fields.Char('Description')
    uom_id = fields.Many2one('product.uom', 'UoM', readonly=True)

    @api.onchange('product_id')
    def onchange_product_id(self):
        product_id = self.product_id
        self.uom_id = product_id.uos_id
        self.name = product_id.name
        self.list_price = product_id.list_price

    @api.constrains('product_id')
    def set_product_uom(self):
        self.uom_id = self.product_id.uos_id

    @api.constrains('product_uom_qty', 'list_price')
    def subtotal(self):
        self.price_subtotal = self.product_uom_qty * self.list_price

    @api.onchange('product_uom_qty', 'list_price')
    def compute_subtotal(self):
        self.price_subtotal = self.product_uom_qty * self.list_price


class HotelRoomReservationLine(models.Model):
    _name = 'hotel.room.reservation.line'
    _description = 'Hotel Room Reservation'
    _rec_name = 'room_id'

    room_id = fields.Many2one(comodel_name='hotel.room', string='Room id')
    check_in = fields.Datetime('Check In Date', required=True)
    check_out = fields.Datetime('Check Out Date', required=True)
    state = fields.Selection([('assigned', 'Assigned'),
                              ('unassigned', 'Unassigned')], 'Room Status')
    reservation_id = fields.Many2one('hotel.reservation',
                                     string='Reservation')
    status = fields.Selection(string='state', related='reservation_id.state')


class HotelRoom(models.Model):
    _inherit = 'hotel.room'
    _description = 'Hotel Room'
    _order = 'name asc'

    room_reservation_line_ids = fields.One2many('hotel.room.reservation.line',
                                                'room_id',
                                                string='Room Reserv Line')

    @api.model
    def cron_room_line(self):
        """
        This method is for scheduler
        every 1min scheduler will call this method and check Status of
        room is occupied or available
        --------------------------------------------------------------
        @param self: The object pointer
        @return: update status of hotel room reservation line
        """
        reservation_line_obj = self.env['hotel.room.reservation.line']
        folio_room_line_obj = self.env['folio.room.line']
        now = datetime.datetime.now()
        curr_date = now.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        for room in self.search([]):
            reserv_line_ids = [reservation_line.ids for
                               reservation_line in
                               room.room_reservation_line_ids]
            reserv_args = [('id', 'in', reserv_line_ids),
                           ('check_in', '<=', curr_date),
                           ('check_out', '>=', curr_date)]
            reservation_line_ids = reservation_line_obj.search(reserv_args)
            rooms_ids = [room_line.ids for room_line in room.room_line_ids]
            rom_args = [('id', 'in', rooms_ids),
                        ('check_in', '<=', curr_date),
                        ('check_out', '>=', curr_date)]
            room_line_ids = folio_room_line_obj.search(rom_args)
            status = {'isroom': True, 'color': 5}
            if reservation_line_ids.ids:
                status = {'isroom': False, 'color': 2}
            room.write(status)
            if room_line_ids.ids:
                status = {'isroom': False, 'color': 2}
            room.write(status)
            if reservation_line_ids.ids and room_line_ids.ids:
                raise except_orm(_('Wrong Entry'),
                                 _('Please Check Rooms Status \
                                 for %s.' % (room.name)))
        return True


class RoomReservationSummary(models.Model):
    _name = 'room.reservation.summary'
    _description = 'Room reservation summary'

    date_from = fields.Datetime('Date From')
    date_to = fields.Datetime('Date To')
    summary_header = fields.Text('Summary Header')
    room_summary = fields.Text('Room Summary')
    room_type_summary = fields.Many2one('hotel.room.type', string="Type",domain="[('categ_id','=',True)]")
    room_category_summary = fields.Many2one('hotel.room.type', string="Category", domain="[('categ_id','=',False)]")

    @api.multi
    def generate_summary(self):
        res = {}
        all_detail = []
        room_obj = self.env['hotel.room']
        reservation_line_obj = self.env['hotel.room.reservation.line']
        folio_room_line_obj = self.env['folio.room.line']
        date_range_list = []
        main_header = []
        summary_header_list = ['Rooms']

        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise except_orm(_('User Error!'),
                                 _('Please Check Time period Date \
                                         From can\'t be greater than Date To !'))
            d_frm_obj = (datetime.datetime.strptime
                         (self.date_from, DEFAULT_SERVER_DATETIME_FORMAT))
            d_to_obj = (datetime.datetime.strptime
                        (self.date_to, DEFAULT_SERVER_DATETIME_FORMAT))
            temp_date = d_frm_obj

            while temp_date <= d_to_obj:
                val = ''
                val = (str(temp_date.strftime("%a")) + ' ' +
                       str(temp_date.strftime("%b")) + ' ' +
                       str(temp_date.strftime("%d")))
                summary_header_list.append(val)
                date_range_list.append(temp_date.strftime
                                       (DEFAULT_SERVER_DATETIME_FORMAT))
                temp_date = temp_date + datetime.timedelta(days=1)
            all_detail.append(summary_header_list)

            room_ids = []
            type_id = self.room_type_summary.id
            category_id = self.room_category_summary.id
            if type_id and category_id:
                room_ids = room_obj.search([('categ_id_2', '=', self.room_type_summary.id),
                                            ('categ_id', '=', self.room_category_summary.id)])
            elif type_id or category_id:
                room_ids = room_obj.search(['|',('categ_id_2', '=', self.room_type_summary.id),
                                            ('categ_id', '=', self.room_category_summary.id)])
            else:
                room_ids = room_obj.search([])

            all_room_detail = []
            for room in room_ids:
                room_detail = {}
                room_list_stats = []
                room_detail.update({'name': room.name or ''})
                if not room.room_reservation_line_ids and \
                        not room.room_line_ids:
                    for chk_date in date_range_list:
                        room_list_stats.append({'state': 'Free',
                                                'date': chk_date})
                else:
                    for chk_date in date_range_list:
                        reserline_ids = room.room_reservation_line_ids.ids
                        reservline_ids = (reservation_line_obj.search
                                          ([('id', 'in', reserline_ids),
                                            ('check_in', '<=', chk_date),
                                            ('check_out', '>=', chk_date),
                                            ('status', '!=', 'cancel')
                                            ]))
                        fol_room_line_ids = room.room_line_ids.ids
                        folio_resrv_ids = (folio_room_line_obj.search
                                           ([('id', 'in', fol_room_line_ids),
                                             ('check_in', '<=', chk_date),
                                             ('check_out', '>=', chk_date),
                                             ('status', '!=', 'cancel')
                                             ]))
                        if reservline_ids or folio_resrv_ids:
                            ##### PISEY KORN ADDED ####################################################
                            name = ""
                            room_name = ""
                            check_in = ""
                            check_out = ""
                            reservation = []
                            try:
                                if reserline_ids:
                                    name = reservline_ids.reservation_id.partner_id.name
                                if folio_resrv_ids:
                                    name = folio_resrv_ids.folio_id.partner_id.name
                            except Exception, e:
                                arr = []
                                id = ""
                                for i in e.value:
                                    if i.isdigit():
                                        id = id + i
                                    if i == ',':
                                        arr.append(int(id))
                                        id = ""
                                if int(id) not in arr and int(id) != "":
                                    arr.append(int(id))
                                if "hotel.room.reservation.line" in e.value:
                                    obj = reservation_line_obj.browse(arr)
                                    for line in obj:
                                        check_in = parse(line.check_in).date()
                                        check_out = parse(line.check_out).date()
                                        room_name = line.room_id.name
                                        reservation.append(line.reservation_id.reservation_no)
                                if "folio.room.line" in e.value:
                                    obj = folio_room_line_obj.browse(arr)
                                    for line in obj:
                                        check_in = parse(line.check_in).date()
                                        check_out = parse(line.check_out).date()
                                        room_name = line.room_id.name
                                        reservation.append(line.reservation_id.reservation_no)
                                raise except_orm(_('Error'), _(
                                    'There is duplicated reservations \n Room: %s \n Check In: %s \n Check Out: %s \n Reservation: %s , %s' % (
                                    room_name, str(check_in), str(check_out), reservation[0], reservation[1])))
                            #########################################################################################
                            room_list_stats.append({
                                'state': name,
                                'date': chk_date,
                                'room_id': room.id,
                                'is_draft': 'No',
                                'data_model': '',
                                'data_id': 0})
                        else:
                            room_list_stats.append({'state': 'Free',
                                                    'date': chk_date,
                                                    'room_id': room.id})
                room_detail.update({'value': room_list_stats})
                all_room_detail.append(room_detail)
            main_header.append({'header': summary_header_list})
            self.summary_header = str(main_header)
            self.room_summary = str(all_room_detail)

    @api.model
    def default_get(self, fields):
        """
        To get default values for the object.
        @param self: The object pointer.
        @param fields: List of fields for which we want default values
        @return: A dictionary which of fields with values.
        """
        if self._context is None:
            self._context = {}
        res = super(RoomReservationSummary, self).default_get(fields)
        # Added default datetime as today and date to as today + 30.
        from_dt_bef = datetime.datetime.today()
        from_dt = from_dt_bef - relativedelta(days=1)
        t = from_dt.replace(hour=16, minute=00, second=00)
        t1 = t.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        to_dt = t + relativedelta(days=5)
        dt_to = to_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        res.update({'date_from': t1, 'date_to': dt_to})

        if not self.date_from and self.date_to:
            date_today = datetime.datetime.today()
            first_day = datetime.datetime(date_today.year,
                                          date_today.month, 1, 0, 0, 0)
            first_temp_day = first_day + relativedelta(months=1)
            last_temp_day = first_temp_day - relativedelta(days=1)
            last_day = datetime.datetime(last_temp_day.year,
                                         last_temp_day.month,
                                         last_temp_day.day, 23, 59, 59)
            date_froms = first_day.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            date_ends = last_day.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            res.update({'date_from': date_froms, 'date_to': date_ends})
        return res

    @api.multi
    def room_reservation(self):
        '''
        @param self: object pointer
        '''
        mod_obj = self.env['ir.model.data']
        if self._context is None:
            self._context = {}
        model_data_ids = mod_obj.search([('model', '=', 'ir.ui.view'),
                                         ('name', '=',
                                          'view_hotel_reservation_form')])
        resource_id = model_data_ids.read(fields=['res_id'])[0]['res_id']
        return {'name': _('Reconcile Write-Off'),
                'context': self._context,
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'hotel.reservation',
                'views': [(resource_id, 'form')],
                'type': 'ir.actions.act_window',
                'target': 'new',
                }


class QuickRoomReservation(models.TransientModel):
    _name = 'quick.room.reservation'
    _description = 'Quick Room Reservation'

    partner_id = fields.Many2one('res.partner', string="Customer",
                                 required=True)
    check_in = fields.Datetime('Check In', required=True)
    check_out = fields.Datetime('Check Out', required=True)
    room_id = fields.Many2one('hotel.room', 'Room', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Hotel', required=True)
    pricelist_id = fields.Many2one('product.pricelist', 'pricelist',
                                   required=True)
    partner_invoice_id = fields.Many2one('res.partner', 'Invoice Address',
                                         required=True)
    partner_order_id = fields.Many2one('res.partner', 'Ordering Contact',
                                       required=True)
    partner_shipping_id = fields.Many2one('res.partner', 'Delivery Address',
                                          required=True)

    @api.onchange('check_out', 'check_in')
    def on_change_check_out(self):
        '''
        When you change checkout or checkin it will check whether
        Checkout date should be greater than Checkin date
        and update dummy field
        -----------------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        if self.check_out and self.check_in:
            if self.check_out < self.check_in:
                raise except_orm(_('Warning'),
                                 _('Checkout date should be greater \
                                 than Checkin date.'))

    @api.onchange('partner_id')
    def onchange_partner_id_res(self):
        '''
        When you change partner_id it will update the partner_invoice_id,
        partner_shipping_id and pricelist_id of the hotel reservation as well
        ---------------------------------------------------------------------
        @param self: object pointer
        '''
        if not self.partner_id:
            self.partner_invoice_id = False
            self.partner_shipping_id = False
            self.partner_order_id = False
        else:
            addr = self.partner_id.address_get(['delivery', 'invoice',
                                                'contact'])
            self.partner_invoice_id = addr['invoice']
            self.partner_order_id = addr['contact']
            self.partner_shipping_id = addr['delivery']
            self.pricelist_id = self.partner_id.property_product_pricelist.id

    @api.model
    def default_get(self, fields):
        """
        To get default values for the object.
        @param self: The object pointer.
        @param fields: List of fields for which we want default values
        @return: A dictionary which of fields with values.
        """
        if self._context is None:
            self._context = {}
        res = super(QuickRoomReservation, self).default_get(fields)
        if self._context:
            keys = self._context.keys()
            if 'date' in keys:
                res.update({'check_in': self._context['date']})
            if 'room_id' in keys:
                roomid = self._context['room_id']
                res.update({'room_id': int(roomid)})
        return res

    @api.multi
    def room_reserve(self):
        """
        This method create a new record for hotel.reservation
        -----------------------------------------------------
        @param self: The object pointer
        @return: new record set for hotel reservation.
        """
        hotel_res_obj = self.env['hotel.reservation']
        for res in self:
            rec = (hotel_res_obj.create
                   ({'partner_id': res.partner_id.id,
                     'partner_invoice_id': res.partner_invoice_id.id,
                     'partner_order_id': res.partner_order_id.id,
                     'partner_shipping_id': res.partner_shipping_id.id,
                     'checkin': res.check_in,
                     'checkout': res.check_out,
                     'warehouse_id': res.warehouse_id.id,
                     'pricelist_id': res.pricelist_id.id,
                     'reservation_line': [(0, 0,
                                           {'reserve': [(6, 0,
                                                         [res.room_id.id])],
                                            'name': (res.room_id and
                                                     res.room_id.name or '')
                                            })]
                     }))
        return rec
