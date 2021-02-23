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
import datetime
from openerp import models, fields, api


class HotelReservationWizard(models.TransientModel):

    _name = 'hotel.reservation.wizard'

    date_start = fields.Datetime('Start Date', required=True)
    date_end = fields.Datetime('End Date', required=True)

    @api.multi
    def _get_checkin_date(self):
        checkin = datetime.datetime.now().strftime("%Y-%m-%d 07:00:00")
        return checkin

    @api.multi
    def _get_checkout_date(self):
        out =  datetime.datetime.now()+ datetime.timedelta(days=1)
        checkout = out.strftime("%Y-%m-%d 05:00:00")
        return checkout

    _defaults = {
        'date_start': _get_checkin_date,
        'date_end': _get_checkout_date,
    }

    @api.multi
    def report_reservation_detail(self):
        data = {
            'ids': self.ids,
            'model': 'hotel.reservation',
            'form': self.read(['date_start', 'date_end'])[0]
        }
        return self.env['report'
                        ].get_action(self,
                                     'hotel_reservation.report_roomres_qweb',
                                     data=data)

    @api.multi
    def report_checkin_detail(self):
        data = {
            'ids': self.ids,
            'model': 'hotel.reservation',
            'form': self.read(['date_start', 'date_end'])[0],
        }
        return self.env['report'
                        ].get_action(self,
                                     'hotel_reservation.report_checkin_qweb',
                                     data=data)

    @api.multi
    def report_checkout_detail(self):
        data = {
            'ids': self.ids,
            'model': 'hotel.reservation',
            'form': self.read(['date_start', 'date_end'])[0]
        }
        return self.env['report'
                        ].get_action(self,
                                     'hotel_reservation.report_checkout_qweb',
                                     data=data)

    @api.multi
    def report_maxroom_detail(self):
        data = {
            'ids': self.ids,
            'model': 'hotel.reservation',
            'form': self.read(['date_start', 'date_end'])[0]
        }
        return self.env['report'
                        ].get_action(self,
                                     'hotel_reservation.report_maxroom_qweb',
                                     data=data)


class MakeFolioWizard(models.TransientModel):

    _name = 'wizard.make.folio'

    grouped = fields.Boolean('Group the Folios')

    @api.multi
    def makeFolios(self):
        order_obj = self.env['hotel.reservation']
        newinv = []
        for order in order_obj.browse(self._context['active_ids']):
            for folio in order.folio_id:
                newinv.append(folio.id)
        return {
            'domain': "[('id','in', [" + ','.join(map(str, newinv)) + "])]",
            'name': 'Folios',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hotel.folio',
            'view_id': False,
            'type': 'ir.actions.act_window'
        }
