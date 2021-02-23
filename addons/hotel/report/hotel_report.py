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

import time

import dateutil

from openerp import models
from openerp.report import report_sxw


class FolioReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(FolioReport, self).__init__(cr, uid, name, context)
        self.localcontext.update({'time': time,
                                  'get_data': self.get_data,
                                  'apartment_data': self.apartment_data,
                                  'daily_data': self.daily_data,
                                  'payment_data': self.payment_data,
                                  'get_Total': self.getTotal,
                                  'get_total': self.gettotal,
                                  })
        self.temp = 0.0

    def get_data(self, date_start, date_end):
        folio_obj = self.pool.get('hotel.folio')
        tids = folio_obj.search(self.cr, self.uid,
                                [('checkin_date', '>=', date_start),
                                 ('checkout_date', '<=', date_end),
                                 ('state', '!=', 'cancel'),
                                 ])

        res = []
        folio_ids = folio_obj.browse(self.cr, self.uid, tids)

        for folio in folio_ids:
            folio_data = {}
            folio_data['name'] = folio.name
            folio_data['user_id'] = folio.user_id.name
            folio_data['memo'] = folio.memo
            folio_data['acco'] = folio.acco_tax
            folio_data['vat'] = folio.vat_tax
            folio_data['partner'] = folio.partner_id.name
            if folio.partner_id.parent_id:
                folio_data['company_name'] = folio.partner_id.parent_id.name
            folio_data['total'] = folio.amount_total
            folio_data['checkin'] = dateutil.parser.parse(folio.checkin_date).date()
            folio_data['checkout'] = dateutil.parser.parse(folio.checkout_date).date()
            folio_data.update({'payment': {}})

            room_price = 0
            room_data = []
            for line in folio.room_lines:
                d ={}
                d['room_no'] = line.room_no.name
                d['price'] = line.price_unit
                room_data.append(d)
                room_price = room_price + line.price_unit*line.product_uom_qty

            total_other = 0
            spa = 0
            bus = 0
            for ser_line in folio.service_lines:
                if ser_line.product_id.name == 'SPA':
                    # print "-------1", ser_line.product_id.name
                    spa = spa + ser_line.price_unit * ser_line.product_uom_qty
                if ser_line.product_id.name == 'Airport Bus':
                    bus = bus + ser_line.price_unit * ser_line.product_uom_qty
                else:
                    # print "--------", ser_line.product_id.name
                    total_other = total_other + ser_line.price_unit * ser_line.product_uom_qty

            folio_data['total_room'] = room_price
            folio_data['spa'] = spa
            folio_data['bus'] = bus
            folio_data['total_other'] = total_other
            folio_data.update({'room': room_data})

            if folio.state == 'draft':
                folio_data['payment'].update({'city': 0.0, 'invoice': " "})

            else:
                payment_method = {}
                for payment_line in folio.hotel_invoice_id.payment_ids:
                    name = payment_line.journal_id.name

                    if name in payment_method:
                        payment_method[name] += payment_line.credit
                    else:
                        payment_method.update({name: payment_line.credit})

                for p_n in payment_method:
                    folio_data['payment'].update({p_n: payment_method[p_n]})
                folio_data['payment'].update(
                    {'city': folio.hotel_invoice_id.residual, 'invoice': folio.hotel_invoice_id.number,
                     'date': folio.hotel_invoice_id.date_invoice})

            res.append(folio_data)
        newlist = sorted(res, key=lambda k: k['payment']['invoice'])
        return newlist

    # Report for hotel apartment Nun Sophanon
    def apartment_data(self, report_date):
        # report_date = dateutil.parser.parse(report_date).date()
        folio_obj = self.pool.get('hotel.folio')
        tids = folio_obj.search(self.cr, self.uid,
                                [('checkin_date', '=', report_date),
                                 ('state', '!=', 'cancel'),
                                 ])
        res = []
        folio_ids = folio_obj.browse(self.cr, self.uid, tids)

        for folio in folio_ids:
            folio_data = {}
            folio_data['name'] = folio.name
            folio_data['user_id'] = folio.user_id.name
            folio_data['memo'] = folio.memo
            folio_data['acco'] = folio.acco_tax
            folio_data['vat'] = folio.vat_tax
            folio_data['partner'] = folio.partner_id.name
            if folio.partner_id.parent_id:
                folio_data['company_name'] = folio.partner_id.parent_id.name
            folio_data['total'] = folio.amount_total
            folio_data['checkin'] = dateutil.parser.parse(folio.checkin_date).date()
            folio_data['checkout'] = dateutil.parser.parse(folio.checkout_date).date()
            folio_data.update({'payment': {}})

            room_price = 0
            room_data = []
            for line in folio.room_lines:
                d = {}
                d['room_no'] = line.room_no.name
                d['price'] = line.price_unit
                room_data.append(d)
                room_price = room_price + line.price_unit * line.product_uom_qty

            total_other = 0
            spa = 0
            bus = 0
            for ser_line in folio.service_lines:
                if ser_line.product_id.name == 'SPA':
                    # print "-------1", ser_line.product_id.name
                    spa = spa + ser_line.price_unit * ser_line.product_uom_qty
                if ser_line.product_id.name == 'Airport Bus':
                    bus = bus + ser_line.price_unit * ser_line.product_uom_qty
                else:
                    # print "--------", ser_line.product_id.name
                    total_other = total_other + ser_line.price_unit * ser_line.product_uom_qty

            folio_data['total_room'] = room_price
            folio_data['spa'] = spa
            folio_data['bus'] = bus
            folio_data['total_other'] = total_other
            folio_data.update({'room': room_data})

            if folio.state == 'draft':
                folio_data['payment'].update({'city': 0.0, 'invoice': " "})

            else:
                payment_method = {}
                for payment_line in folio.hotel_invoice_id.payment_ids:
                    name = payment_line.journal_id.name

                    if name in payment_method:
                        payment_method[name] += payment_line.credit
                    else:
                        payment_method.update({name: payment_line.credit})

                for p_n in payment_method:
                    folio_data['payment'].update({p_n: payment_method[p_n]})
                folio_data['payment'].update(
                    {'city': folio.hotel_invoice_id.residual, 'invoice': folio.hotel_invoice_id.number,
                     'date': folio.hotel_invoice_id.date_invoice})

            if folio.apartment:
                res.append(folio_data)
        newlist = sorted(res, key=lambda k: k['payment']['invoice'])
        return newlist

    # Report for hotel Daily Nun Sophanon
    def daily_data(self, report_date):
        folio_obj = self.pool.get('hotel.folio')

        tids = folio_obj.search(self.cr, self.uid,
                                [('checkin_date', '<=', report_date),
                                 ('checkout_date', '>=', report_date),
                                 ('state', '!=', 'cancel'),
                                 ])

        res = []
        folio_ids = folio_obj.browse(self.cr, self.uid, tids)

        for folio in folio_ids:
            folio_data = {}
            folio_data['name'] = folio.name
            folio_data['user_id'] = folio.user_id.name
            folio_data['memo'] = folio.memo
            folio_data['acco'] = folio.acco_tax
            folio_data['vat'] = folio.vat_tax
            folio_data['partner'] = folio.partner_id.name
            # print "-----------------------", folio.partner_id.parent_id
            if folio.partner_id.parent_id:
                folio_data['company_name'] = folio.partner_id.parent_id.name
            folio_data['total'] = folio.amount_total
            folio_data['checkin'] = dateutil.parser.parse(folio.checkin_date).date()
            folio_data['checkout'] = dateutil.parser.parse(folio.checkout_date).date()
            folio_data.update({'payment': {}})

            room_price = 0
            room_data = []
            for line in folio.room_lines:
                d = {}
                d['room_no'] = line.room_no.name
                d['price'] = line.price_unit
                room_data.append(d)
                room_price = room_price + line.price_unit * line.product_uom_qty

            total_other = 0
            spa = 0
            bus = 0
            for ser_line in folio.service_lines:
                if ser_line.product_id.name == 'SPA':
                    # print "-------1", ser_line.product_id.name
                    spa = spa + ser_line.price_unit * ser_line.product_uom_qty
                if ser_line.product_id.name == 'Airport Bus':
                    bus = bus + ser_line.price_unit * ser_line.product_uom_qty
                else:
                    # print "--------", ser_line.product_id.name
                    total_other = total_other + ser_line.price_unit * ser_line.product_uom_qty

            folio_data['total_room'] = room_price
            folio_data['spa'] = spa
            folio_data['bus'] = bus
            folio_data['total_other'] = total_other
            folio_data.update({'room': room_data})

            if folio.state == 'draft':
                folio_data['payment'].update({'city': 0.0, 'invoice': " "})

            else:
                payment_method = {}
                for payment_line in folio.hotel_invoice_id.payment_ids:
                    name = payment_line.journal_id.name

                    if name in payment_method:
                        payment_method[name] += payment_line.credit
                    else:
                        payment_method.update({name: payment_line.credit})

                for p_n in payment_method:
                    folio_data['payment'].update({p_n: payment_method[p_n]})
                folio_data['payment'].update(
                    {'city': folio.hotel_invoice_id.residual, 'invoice': folio.hotel_invoice_id.number,
                     'date': folio.hotel_invoice_id.date_invoice})

            if not folio.apartment:
                res.append(folio_data)

        # print "----res", res
        newlist = sorted(res, key=lambda k: k['payment']['invoice'])

        return newlist

    #payment items Nun Sophanon
    def payment_data(self, report_date):
        report_date = dateutil.parser.parse(report_date).date()
        payment_obj = self.pool.get('account.voucher')
        invoice_obj = self.pool.get('account.invoice')
        inv_tids = invoice_obj.search(self.cr, self.uid, [])
        tids = payment_obj.search(self.cr, self.uid,
                                [('date', '=', report_date)])
        res = []
        payment_ids = payment_obj.browse(self.cr, self.uid, tids)
        invoice_ids = invoice_obj.browse(self.cr, self.uid, inv_tids)

        for payment_item in payment_ids:
            ref =  payment_item.move_ids[0].ref
            item = {}
            found = False
            for inv in invoice_ids:
                if inv.payment_ids:
                    for pay in inv.payment_ids:
                        if ref == pay.ref:
                            found = True
                            item['date'] = payment_item.date
                            item['number'] = payment_item.number
                            item['amount'] = payment_item.amount
                            item['journal'] = payment_item.journal_id.name
                            item['inv_number'] = inv.number
                            item['subtotal'] = inv.amount_untaxed
                            item['tax'] = inv.amount_tax
                            item['state'] = inv.state
                            item['total'] = inv.amount_total
                            item['balance'] = inv.residual
                            item['inv_date'] = inv.date_invoice
                            item['folio_no'] = inv.folio_no.name
                            item['customer'] = inv.partner_id.name

            if found:
                res.append(item)
        # print "--------", res
        return sorted(res)

    def gettotal(self, total):
        self.temp = self.temp + float(total)
        return total

    def getTotal(self):
        return self.temp


class ReportLunchorder(models.AbstractModel):
    _name = 'report.hotel.report_hotel_folio'
    _inherit = 'report.abstract_report'
    _template = 'hotel.report_hotel_folio'
    _wrapped_report_class = FolioReport


class ReportLunchorderApartment(models.AbstractModel):
    _name = 'report.hotel.report_hotel_folio_apartment'
    _inherit = 'report.abstract_report'
    _template = 'hotel.report_hotel_folio_apartment'
    _wrapped_report_class = FolioReport


class ReportLunchorderDaily(models.AbstractModel):
    _name = 'report.hotel.report_hotel_folio_daily'
    _inherit = 'report.abstract_report'
    _template = 'hotel.report_hotel_folio_daily'
    _wrapped_report_class = FolioReport


class ReceiptRestaurant(models.AbstractModel):
    _name = 'report.hotel.folio_restaurant_receipt'
    _inherit = 'report.abstract_report'
    _template = 'hotel.folio_restaurant_receipt'
    _wrapped_report_class = FolioReport