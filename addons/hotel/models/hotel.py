from openerp.exceptions import except_orm, ValidationError
from openerp.exceptions import Warning as UserError
from openerp.tools import misc, DEFAULT_SERVER_DATETIME_FORMAT
from openerp import models, fields, api, _
from openerp import workflow
from decimal import Decimal
import datetime
import urllib2
import time
from dateutil.parser import parse
import json


def _offset_format_timestamp1(src_tstamp_str, src_format, dst_format,
                              ignore_unparsable_time=True, context=None):
    """
    Convert a source timeStamp string into a destination timeStamp string,
    attempting to apply the
    correct offset if both the server and local timeZone are recognized,or no
    offset at all if they aren't or if tz_offset is false (i.e. assuming they
    are both in the same TZ).

    @param src_tstamp_str: the STR value containing the timeStamp.
    @param src_format: the format to use when parsing the local timeStamp.
    @param dst_format: the format to use when formatting the resulting
     timeStamp.
    @param server_to_client: specify timeZone offset direction (server=src
                             and client=dest if True, or client=src and
                             server=dest if False)
    @param ignore_unparsable_time: if True, return False if src_tstamp_str
                                   cannot be parsed using src_format or
                                   formatted using dst_format.

    @return: destination formatted timestamp, expressed in the destination
             timezone if possible and if tz_offset is true, or src_tstamp_str
             if timezone offset could not be determined.
    """
    if not src_tstamp_str:
        return False
    res = src_tstamp_str
    if src_format and dst_format:
        try:
            # dt_value needs to be a datetime.datetime object\
            # (so notime.struct_time or mx.DateTime.DateTime here!)
            dt_value = datetime.datetime.strptime(src_tstamp_str, src_format)
            if context.get('tz', False):
                try:
                    import pytz
                    src_tz = pytz.timezone(context['tz'])
                    dst_tz = pytz.timezone('UTC')
                    src_dt = src_tz.localize(dt_value, is_dst=True)
                    dt_value = src_dt.astimezone(dst_tz)
                except Exception:
                    pass
            res = dt_value.strftime(dst_format)
        except Exception:
            # Normal ways to end up here are if strptime or strftime failed
            if not ignore_unparsable_time:
                return False
            pass
    return res


class HotelFloor(models.Model):
    _name = "hotel.floor"
    _description = "Floor"

    name = fields.Char('Floor Name', size=64, required=True, select=True)
    sequence = fields.Integer('Sequence', size=64)


class ProductCategory(models.Model):
    _inherit = "product.category"

    isroomtype = fields.Boolean('Is Room Type')
    isamenitytype = fields.Boolean('Is Amenities Type')
    isservicetype = fields.Boolean('Is Service Type')


class HotelRoomType(models.Model):
    _name = "hotel.room.type"
    _description = "Room Type"

    name = fields.Char('Name', size=64, required=True)
    categ_id = fields.Boolean('Is Room Type',required=True)


class ProductProduct(models.Model):
    _inherit = "product.product"

    isroom = fields.Boolean('Is Room')
    iscategid = fields.Boolean('Is categ id')
    isservice = fields.Boolean('Is Service id')


class HotelRoomAmenitiesType(models.Model):
    _name = 'hotel.room.amenities.type'
    _description = 'amenities Type'

    cat_id = fields.Many2one('product.category', 'category', required=True,
                             delegate=True, ondelete='cascade')


class HotelRoomAmenities(models.Model):
    _name = 'hotel.room.amenities'
    _description = 'Room amenities'

    room_categ_id = fields.Many2one('product.product', 'Product Category',
                                    required=True, delegate=True,
                                    ondelete='cascade')
    rcateg_id = fields.Many2one('hotel.room.amenities.type',
                                'Amenity Catagory')


class FolioRoomLine(models.Model):
    _name = 'folio.room.line'
    _description = 'Hotel Room Reservation'
    _rec_name = 'room_id'

    room_id = fields.Many2one(comodel_name='hotel.room', string='Room id')
    check_in = fields.Datetime('Check In Date', required=True)
    check_out = fields.Datetime('Check Out Date', required=True)
    folio_id = fields.Many2one('hotel.folio', string='Folio Number')
    status = fields.Selection(string='state', related='folio_id.state')


class HotelRoom(models.Model):
    _name = 'hotel.room'
    _description = 'Hotel Room'

    product_id = fields.Many2one('product.product', 'Product_id',
                                 required=True, delegate=True,
                                 ondelete='cascade')
    floor_id = fields.Many2one('hotel.floor', 'Floor No',
                               help='At which floor the room is located.')
    max_adult = fields.Integer('Max Adult')
    max_child = fields.Integer('Max Child')
    categ_id = fields.Many2one('hotel.room.type', string='Category',domain="[('categ_id','=',False)]")
    room_amenities = fields.Many2many('hotel.room.amenities', 'temp_tab',
                                      'room_amenities', 'rcateg_id',
                                      string='Room Amenities',
                                      help='List of room amenities. ')
    status = fields.Selection([('available', 'Available'),
                               ('occupied', 'Occupied')],
                              'Status', default='available')
    capacity = fields.Integer('Capacity')
    room_line_ids = fields.One2many('folio.room.line', 'room_id',
                                    string='Room Reservation Line')

    categ_id_2 = fields.Many2one('hotel.room.type', string='Room Type', domain="[('categ_id','=',True)]")


    @api.model
    def create(self, vals):
        uom_obj = self.env['product.uom']
        vals.update({'type': 'service'})
        uom_rec = uom_obj.search([('name', 'ilike', 'Hour(s)')], limit=1)
        if uom_rec:
            vals.update({'uom_id': uom_rec.id, 'uom_po_id': uom_rec.id})
        return super(HotelRoom, self).create(vals)

    @api.onchange('isroom')
    def isroom_change(self):
        '''
        Based on isroom, status will be updated.
        ----------------------------------------
        @param self: object pointer
        '''
        if self.isroom is False:
            self.status = 'occupied'
        if self.isroom is True:
            self.status = 'available'

    # @api.multi
    # def write(self, vals):
    #     """
    #     Overrides orm write method.
    #     @param self: The object pointer
    #     @param vals: dictionary of fields value.
    #     """
    #     if 'isroom' in vals and vals['isroom'] is False:
    #         vals.update({'color': 2, 'status': 'occupied'})
    #     if 'isroom' in vals and vals['isroom'] is True:
    #         vals.update({'color': 5, 'status': 'available'})
    #     ret_val = super(HotelRoom, self).write(vals)
    #     return ret_val

    @api.multi
    def set_room_status_occupied(self):
        """
        This method is used to change the state
        to occupied of the hotel room.
        ---------------------------------------
        @param self: object pointer
        """
        return self.write({'isroom': False, 'color': 2})

    @api.multi
    def set_room_status_available(self):
        """
        This method is used to change the state
        to available of the hotel room.
        ---------------------------------------
        @param self: object pointer
        """
        return self.write({'isroom': True, 'color': 5})


class HotelFolio(models.Model):

    @api.multi
    def name_get(self):
        res = []
        disp = ''
        for rec in self:
            if rec.order_id:
                disp = str(rec.name)
                res.append((rec.id, disp))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        args += ([('name', operator, name)])
        mids = self.search(args, limit=100)
        return mids.name_get()

    @api.model
    def _needaction_count(self, domain=None):
        """
         Show a count of draft state folio on the menu badge.
         @param self: object pointer
        """
        return self.search_count([('state', '=', 'draft')])

    @api.model
    def _get_checkin_date(self):
        if self._context.get('tz'):
            to_zone = self._context.get('tz')
        else:
            to_zone = 'UTC'
        return _offset_format_timestamp1(time.strftime("%Y-%m-%d 14:00:00"),
                                         '%Y-%m-%d %H:%M:%S',
                                         '%Y-%m-%d %H:%M:%S',
                                         ignore_unparsable_time=True,
                                         context={'tz': to_zone})

    @api.model
    def _get_checkout_date(self):
        if self._context.get('tz'):
            to_zone = self._context.get('tz')
        else:
            to_zone = 'UTC'
        tm_delta = datetime.timedelta(days=1)
        return datetime.datetime.strptime(_offset_format_timestamp1
                                          (time.strftime("%Y-%m-%d 12:00:00"),
                                           '%Y-%m-%d %H:%M:%S',
                                           '%Y-%m-%d %H:%M:%S',
                                           ignore_unparsable_time=True,
                                           context={'tz': to_zone}),
                                          '%Y-%m-%d %H:%M:%S') + tm_delta

    @api.multi
    def copy(self, default=None):
        '''
        @param self: object pointer
        @param default: dict of default values to be set
        '''
        res = {}
        try:
            res = super(HotelFolio, self).copy(default=default)
        except Exception, e:
            raise UserError(_('You can not copy this folio because %s') % e)
        return res

    @api.multi
    def _invoiced(self, name, arg):
        '''
        @param self: object pointer
        @param name: Names of fields.
        @param arg: User defined arguments
        '''
        return self.env['sale.order']._invoiced(name, arg)

    @api.multi
    def _invoiced_search(self, obj, name, args):
        '''
        @param self: object pointer
        @param name: Names of fields.
        @param arg: User defined arguments
        '''
        return self.env['sale.order']._invoiced_search(obj, name, args)

    _name = 'hotel.folio'
    _description = 'hotel folio new'
    _rec_name = 'order_id'
    _order = 'id'
    _inherit = ['ir.needaction_mixin']

    name = fields.Char('Folio Number', readonly=True)
    order_id = fields.Many2one('sale.order', 'Order', delegate=True,
                               required=True, ondelete='cascade')
    checkin_date = fields.Datetime('Check In', required=True, readonly=True,
                                   default=_get_checkin_date)
    checkout_date = fields.Datetime('Check Out', required=True, readonly=True,
                                    default=_get_checkout_date)
    room_lines = fields.One2many('hotel.folio.line', 'folio_id',
                                 readonly=True,
                                 states={'draft': [('readonly', False)],
                                         'sent': [('readonly', False)]},
                                 help="Hotel room reservation detail.")
    service_lines = fields.One2many('hotel.service.line', 'folio_id',
                                    readonly=True,
                                    states={'draft': [('readonly', False)],
                                            'sent': [('readonly', False)]},
                                    help="Hotel services detail provide to"
                                         "customer and it will include in "
                                         "main Invoice.")
    restaurant_lines = fields.One2many('hotel.restaurant.line', 'restaurant_line_id',
                                       readonly=True,
                                       states={'draft': [('readonly', False)],
                                               'sent': [('readonly', False)]},
                                       help="Hotel restaurant detail provide to"
                                            "customer and it will not include in "
                                            "main Invoice, only in receipt.")

    hotel_policy = fields.Selection([('prepaid', 'On Booking'),
                                     ('manual', 'On Check In'),
                                     ('picking', 'On Checkout')],
                                    'Hotel Policy', default='manual',
                                    help="Hotel policy for payment that "
                                         "either the guest has to payment at "
                                         "booking time or check-in "
                                         "check-out time.")
    duration = fields.Float('Duration in Days',
                            help="Number of days which will automatically "
                                 "count from the check-in and check-out date. ")
    currrency_ids = fields.One2many('currency.exchange', 'folio_no',
                                    readonly=True)
    hotel_invoice_id = fields.Many2one('account.invoice', 'Invoice')

    memo = fields.Char('Memo')
    receipt_no = fields.Char('Receipt No')
    apartment = fields.Boolean('Apartment', readonly=True,
                               states={'draft': [('readonly', False)]})
    # PISEY KORN ADDED #################################################################
    vat_tax = fields.Float('VAT (10%)', readonly=True, compute="compute_acco_vat")
    acco_tax = fields.Float('ACCO (2%)', readonly=True, compute="compute_acco_vat")

    @api.one
    def compute_acco_vat(self):
        sub_total = 0
        for line in self.room_lines:
            acc_found = False
            for tax in line.tax_id:
                if "ACCO" in tax.name:
                    acc_found = True
            if acc_found:
                sub_total = sub_total + line.price_subtotal
        self.acco_tax = sub_total * 0.02
        self.vat_tax = self.amount_tax - sub_total * 0.02

    @api.constrains('pricelist_id')
    def compute_price_list(self):
        price_list_id = self.pricelist_id
        for line in self.room_lines:
            for item in price_list_id.version_id.items_id:
                if item.categ_id.name == line.room_no.categ_id.name:
                    line.price_unit = line.room_no.list_price + item.price_surcharge
    ####################################################################################

    @api.constrains('checkin_date', 'checkout_date')
    def update_checkin_checkout_date(self):
        for line in self.room_lines:
            line.checkin_date = self.checkin_date
            line.checkout_date = self.checkout_date

    @api.multi
    def go_to_currency_exchange(self):
        '''
         when Money Exchange button is clicked then this method is called.
        -------------------------------------------------------------------
        @param self: object pointer
        '''
        cr, uid, context = self.env.args
        context = dict(context)
        for rec in self:
            if rec.partner_id.id and len(rec.room_lines) != 0:
                context.update({'folioid': rec.id, 'guest': rec.partner_id.id,
                                'room_no': rec.room_lines[0].product_id.name,
                                'hotel': rec.warehouse_id.id})
                self.env.args = cr, uid, misc.frozendict(context)
            else:
                raise except_orm(_('Warning'), _('Please Reserve Any Room.'))
        return {'name': _('Currency Exchange'),
                'res_model': 'currency.exchange',
                'type': 'ir.actions.act_window',
                'view_id': False,
                'view_mode': 'form,tree',
                'view_type': 'form',
                'context': {'default_folio_no': context.get('folioid'),
                            'default_hotel_id': context.get('hotel'),
                            'default_guest_name': context.get('guest'),
                            'default_room_number': context.get('room_no')
                            },
                }

    @api.constrains('room_lines')
    def folio_room_lines(self):
        '''
        This method is used to validate the room_lines.
        ------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        folio_rooms = []
        for room in self[0].room_lines:
            if room.room_no.id in folio_rooms:
                raise ValidationError(_('You Cannot Take Same Room Twice'))
            folio_rooms.append(room.room_no.id)

    @api.constrains('checkin_date', 'checkout_date')
    def check_dates(self):
        '''
        This method is used to validate the checkin_date and checkout_date.
        -------------------------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        if self.checkin_date and self.checkout_date:
            if self.checkin_date >= self.checkout_date:
                raise ValidationError(_('Check in Date Should be \
                less than the Check Out Date!'))
        if self.date_order and self.checkin_date:
            if self.checkin_date <= self.date_order:
                raise ValidationError(_('Check in date should be \
                greater than the current date.'))

    @api.onchange('checkout_date', 'checkin_date')
    def onchange_dates(self):
        '''
        This mathod gives the duration between check in and checkout
        if customer will leave only for some hour it would be considers
        as a whole day.If customer will check in checkout for more or equal
        hours, which configured in company as additional hours than it would
        be consider as full days
        --------------------------------------------------------------------
        @param self: object pointer
        @return: Duration and checkout_date
        '''
        company_obj = self.env['res.company']
        configured_addition_hours = 0
        company_ids = company_obj.search([])
        if company_ids.ids:
            configured_addition_hours = company_ids[0].additional_hours
        myduration = 0
        chckin = self.checkin_date
        chckout = self.checkout_date
        if chckin and chckout:
            server_dt = DEFAULT_SERVER_DATETIME_FORMAT
            chkin_dt = datetime.datetime.strptime(chckin, server_dt)
            chkout_dt = datetime.datetime.strptime(chckout, server_dt)
            dur = chkout_dt - chkin_dt
            sec_dur = dur.seconds
            if (not dur.days and not sec_dur) or (dur.days and not sec_dur):
                myduration = dur.days
            else:
                myduration = dur.days + 1
            if configured_addition_hours > 0:
                additional_hours = abs((dur.seconds / 60) / 60)
                if additional_hours >= configured_addition_hours:
                    myduration += 1
        self.duration = myduration

    @api.model
    def create(self, vals, check=True):
        """
        Overrides orm create method.
        @param self: The object pointer
        @param vals: dictionary of fields value.
        @return: new record set for hotel folio.
        """
        if not 'service_lines' and 'folio_id' in vals:
            tmp_room_lines = vals.get('room_lines', [])
            vals['order_policy'] = vals.get('hotel_policy', 'manual')
            vals.update({'room_lines': []})
            folio_id = super(HotelFolio, self).create(vals)
            for line in (tmp_room_lines):
                line[2].update({'folio_id': folio_id})
            vals.update({'room_lines': tmp_room_lines})
            folio_id.write(vals)
        else:
            if not vals:
                vals = {}
            vals['name'] = self.env['ir.sequence'].get('hotel.folio')
            folio_id = super(HotelFolio, self).create(vals)
        # PISEY KORN ADDED ##########################################################
        price_list_id = folio_id.pricelist_id
        for line in folio_id.room_lines:
            for item in price_list_id.version_id.items_id:
                if item.categ_id.name == line.room_no.categ_id.name:
                    line.price_unit = line.room_no.list_price + item.price_surcharge
        #############################################################################
        return folio_id

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        '''
        When you change warehouse it will update the warehouse of
        the hotel folio as well
        ----------------------------------------------------------
        @param self: object pointer
        '''
        for folio in self:
            order = folio.order_id
            x = order.onchange_warehouse_id(folio.warehouse_id.id)
        return x

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        '''
        When you change partner_id it will update the partner_invoice_id,
        partner_shipping_id and pricelist_id of the hotel folio as well
        ---------------------------------------------------------------
        @param self: object pointer
        '''
        if self.partner_id:
            partner_rec = self.env['res.partner'].browse(self.partner_id.id)
            order_ids = [folio.order_id.id for folio in self]
            if not order_ids:
                self.partner_invoice_id = partner_rec.id
                self.partner_shipping_id = partner_rec.id
                self.pricelist_id = partner_rec.property_product_pricelist.id
                raise UserError(_('Not Any Order\
                                   For  %s ' % (partner_rec.name)))
            else:
                self.partner_invoice_id = partner_rec.id
                self.partner_shipping_id = partner_rec.id
                self.pricelist_id = partner_rec.property_product_pricelist.id

    @api.multi
    def button_dummy(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            order = folio.order_id
            x = order.button_dummy()
        return x

    @api.multi
    def action_invoice_create(self, grouped=False, states=None):
        '''
        @param self: object pointer
        '''
        if states is None:
            states = ['confirmed', 'done']
        order_ids = [folio.order_id.id for folio in self]
        room_lst = []
        sale_obj = self.env['sale.order'].browse(order_ids)
        inv_ids0 = set(inv.id for sale in sale_obj for inv in sale.invoice_ids)
        sale_obj.signal_workflow('manual_invoice')
        inv_ids1 = set(inv.id for sale in sale_obj for inv in sale.invoice_ids)
        # determine newly created invoices
        new_inv_ids = list(inv_ids1 - inv_ids0)
        if new_inv_ids:
            for line in self:
                values = {'invoiced': True,
                          'state': 'progress' if grouped else 'progress',
                          'hotel_invoice_id': new_inv_ids and new_inv_ids[0]
                          }
                line.write(values)
                #            for line2 in line.folio_pos_order_ids:
                #                line2.write({'invoice_id': invoice_id})
                #                line2.action_invoice_state()
                for rec in line.room_lines:
                    room_lst.append(rec.room_no)
                for room in room_lst:
                    room_obj = self.env['hotel.room'
                    ].search([('name', '=', room.name)])
                    room_obj.write({'isroom': True})
            return new_inv_ids and new_inv_ids[0]
        return True

    @api.multi
    def action_invoice_cancel(self):
        '''
        @param self: object pointer
        '''
        order_ids = [folio.order_id.id for folio in self]
        sale_obj = self.env['sale.order'].browse(order_ids)
        res = sale_obj.action_invoice_cancel()
        for sale in self:
            for line in sale.order_line:
                line.write({'invoiced': 'invoiced'})
        sale.write({'state': 'invoice_except'})
        return res

    @api.multi
    def action_invoice_end(self):
        '''
        @param self: object pointer
        '''
        sale_order_obj = self.env['sale.order']
        res = False
        for o in self:
            sale_obj = sale_order_obj.browse([o.order_id.id])
            res = sale_obj.action_invoice_end()
        return res

    @api.multi
    def procurement_needed(self):
        '''
        @param self: object pointer
        '''
        sale_order_obj = self.env['sale.order']
        res = False
        for o in self:
            sale_obj = sale_order_obj.browse([o.order_id.id])
            res = sale_obj.procurement_needed()
        return res

    @api.multi
    def action_done(self):
        '''
        @param self: object pointer
        '''
        return self.order_id.action_done()

    @api.multi
    def action_cancel(self):
        '''
        @param self: object pointer
        '''
        if self._uid not in [user.id for user in self.env['res.groups'].search([('name','=','Hotel Management/ Manager')]).users]:
            raise except_orm(_('Access Error'),
                             _("You are not allow to cancel this record"))
        order_ids = [folio.order_id.id for folio in self]
        sale_obj = self.env['sale.order'].browse(order_ids)
        rv = sale_obj.action_cancel()
        for sale in self:
            for pick in sale.picking_ids:
                workflow.trg_validate(self._uid, 'stock.picking', pick.id,
                                      'button_cancel', self._cr)
            for invoice in sale.invoice_ids:
                workflow.trg_validate(self._uid, 'account.invoice',
                                      invoice.id, 'invoice_cancel',
                                      self._cr)
            sale.write({'state': 'cancel'})
        for line in self.room_lines:
            reservation_obj = line.reservation_id
            if reservation_obj.state != 'cancel':
                room_reservation_line_obj = self.env['hotel.room.reservation.line']
                room_reservation_line = room_reservation_line_obj.search([('reservation_id','=',reservation_obj.id)])
                room_reservation_line.unlink()
        return rv

    @api.multi
    def action_button_confirm(self):
        '''
        @param self: object pointer
        '''
        sale_order_obj = self.env['sale.order']
        res = False
        for o in self:
            sale_obj = sale_order_obj.browse([o.order_id.id])
            res = sale_obj.action_button_confirm()
        return res

    @api.multi
    def action_wait(self):
        '''
        @param self: object pointer
        '''
        sale_order_obj = self.env['sale.order']
        # for o in self:
        #     sale_obj = sale_order_obj.browse([o.order_id.id])
        #     sale_obj.write({'folio_no': o.id, 'receipt_no': o.receipt_no,
        #                     'checkin': o.checkin_date, 'checkout':o.checkout_date})
        #     sale_obj.signal_workflow('order_confirm')
        # return True

        for o in self:
            sale_obj = sale_order_obj.browse([o.order_id.id])
            sale_obj.write({'folio_no': o.id})
            sale_obj.signal_workflow('order_confirm')
        return True

    @api.multi
    def test_state(self, mode):
        '''
        @param self: object pointer
        @param mode: state of workflow
        '''
        write_done_ids = []
        write_cancel_ids = []
        if write_done_ids:
            test_obj = self.env['sale.order.line'].browse(write_done_ids)
            test_obj.write({'state': 'done'})
        if write_cancel_ids:
            test_obj = self.env['sale.order.line'].browse(write_cancel_ids)
            test_obj.write({'state': 'cancel'})

    @api.multi
    def action_ship_create(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            order = folio.order_id
            x = order.action_ship_create()
        return x

    @api.multi
    def action_ship_end(self):
        '''
        @param self: object pointer
        '''
        for order in self:
            order.write({'shipped': True})

    @api.multi
    def has_stockable_products(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            order = folio.order_id
            x = order.has_stockable_products()
        return x

    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        for reserv_rec in self:
            raise ValidationError(_('You can not delete Folio!'))
        return super(HotelFolio, self).unlink()


class HotelFolioLine(models.Model):

    @api.multi
    def _amount_line(self, field_name, arg):
        '''
        @param self: object pointer
        @param field_name: Names of fields.
        @param arg: User defined arguments
        '''
        return self.env['sale.order.line']._amount_line(field_name, arg)

    @api.multi
    def _number_packages(self, field_name, arg):
        '''
        @param self: object pointer
        @param field_name: Names of fields.
        @param arg: User defined arguments
        '''
        return self.env['sale.order.line']._number_packages(field_name, arg)

    @api.model
    def _get_checkin_date(self):
        if 'checkin' in self._context:
            if self._context['checkin']:
                return self._context['checkin']
        if self._context.get('tz'):
            to_zone = self._context.get('tz')
        else:
            to_zone = 'UTC'
        return datetime.datetime.strptime(_offset_format_timestamp1
                                          (time.strftime("%Y-%m-%d 7:00:00"),
                                           '%Y-%m-%d %H:%M:%S',
                                           '%Y-%m-%d %H:%M:%S',
                                           ignore_unparsable_time=True,
                                           context={'tz': to_zone}),
                                          '%Y-%m-%d %H:%M:%S')

    @api.model
    def _get_checkout_date(self):
        if 'checkout' in self._context:
            if self._context['checkout']:
                return self._context['checkout']
        if self._context.get('tz'):
            to_zone = self._context.get('tz')
        else:
            to_zone = 'UTC'
        tm_delta = datetime.timedelta(days=1)
        return datetime.datetime.strptime(_offset_format_timestamp1
                                          (time.strftime("%Y-%m-%d 5:00:00"),
                                           '%Y-%m-%d %H:%M:%S',
                                           '%Y-%m-%d %H:%M:%S',
                                           ignore_unparsable_time=True,
                                           context={'tz': to_zone}),
                                          '%Y-%m-%d %H:%M:%S') + tm_delta

    _name = 'hotel.folio.line'
    _description = 'hotel folio1 room line'

    room_no = fields.Many2one('hotel.room', string='Room No.', required=True)
    order_line_id = fields.Many2one('sale.order.line', string='Order Line',
                                    required=True, delegate=True,
                                    ondelete='cascade')

    folio_id = fields.Many2one('hotel.folio', string='Folio',
                               ondelete='cascade')
    checkin_date = fields.Datetime('Check In', required=True,
                                   default=_get_checkin_date)
    checkout_date = fields.Datetime('Check Out', required=True,
                                    default=_get_checkout_date)
    is_reserved = fields.Boolean('Is Reserved',
                                 help='True when folio line created from \
                                 Reservation')
    reservation_id = fields.Many2one('hotel.reservation', 'Reservation')

    # PISEY KORN ADDED ######################################################################
    @api.onchange('checkin_date', 'checkout_date')
    def on_change_checkin_checkout(self):
        hotel_room_obj = self.env['hotel.room']
        hotel_room_ids = hotel_room_obj.search([])
        room_ids = []
        if not self.checkin_date and self.checkout_date:
            raise except_orm(_('Warning'),
                             _('Before choosing a room,\n You have to select \
                                             a Check in date or a Check out date'))
        checkIn = parse(self.checkin_date)
        checkOut = parse(self.checkout_date)
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
        domain = {'room_no': [('id', 'in', room_ids)]}
        return {'domain': domain}
    #########################################################################################
    @api.model
    def create(self, vals, check=True):
        fol_rm_line_obj = self.env['folio.room.line']
        if 'folio_id' in vals:
            folio = self.env["hotel.folio"].browse(vals['folio_id'])
            vals.update({'order_id': folio.order_id.id})

        # Adding Folio Room line history
        if 'room_no' in vals \
                and 'folio_id' in vals \
                and not vals.get('is_reserved', False):
            prod_room = self.env['hotel.room'].search([('id', '=', vals['room_no'])], limit=1)
            if prod_room:
                rm_line_vals = {'room_id': prod_room.id,
                                'check_in': vals['checkin_date'],
                                'check_out': vals['checkout_date'],
                                'folio_id': vals['folio_id']}

                fol_rm_line_obj.create(rm_line_vals)
                prod_room.write({'isroom': False})
        return super(HotelFolioLine, self).create(vals)

    @api.multi
    def write(self, vals):
        fol_rm_line_obj = self.env['folio.room.line']
        res_room_line_obj = self.env['hotel.room.reservation.line']
        room_obj = self.env['hotel.room']
        prod_id = vals.get('room_no') or self.room_no.id
        folio_id = vals.get('folio_id') or self.folio_id.id
        chkin = vals.get('checkin_date') or self.checkin_date
        chkout = vals.get('checkout_date') or self.checkout_date
        status = vals.get('state') or self.state
        is_reserved = self.is_reserved

        # PISEY KORN ADDED #####################################################################################
        if vals.get('room_no'):
            r = room_obj.browse([vals.get('room_no')])
            checkIn = parse(self.checkin_date)
            checkOut = parse(self.checkout_date)
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
            if available == 0:
                raise except_orm(_('Error!!!'),
                                 _('Room %s is not available for this check in and check out date' % (r.name)))
        ########################################################################################################

        if prod_id and folio_id and not is_reserved:
            prod_room = room_obj.browse([prod_id])
            if (self.room_no and self.folio_id and
                    self.checkin_date and self.checkout_date):
                old_prod_room = self.room_no
                ##############check amendment in folio_lines###############
                if prod_room and old_prod_room:
                    # first check existing room lines
                    srch_rmline = [('room_id', '=', old_prod_room.id),
                                   ('check_in', '=', self.checkin_date),
                                   ('check_out', '=', self.checkout_date),
                                   ('folio_id', '=', self.folio_id.id)]
                    rm_lines = fol_rm_line_obj.search(srch_rmline)
                    if rm_lines:
                        rm_line_vals = {'room_id': prod_room.id,
                                        'check_in': chkin,
                                        'check_out': chkout,
                                        'folio_id': folio_id,
                                        'status': status}
                        rm_lines.write(rm_line_vals)
                        old_prod_room.write({'isroom': True})
                        prod_room.write({'isroom': False})
        else:
            prod_room = room_obj.browse([prod_id])
            if (self.room_no and self.folio_id and
                    self.checkin_date and self.checkout_date):
                old_prod_room = self.room_no
                if prod_room and old_prod_room:
                    srch_rmline = [('room_id', '=', old_prod_room.id),
                                   ('check_in', '=', self.checkin_date),
                                   ('check_out', '=', self.checkout_date),
                                   ('reservation_id', '=', self.folio_id.reservation_id.id)]
                    rm_lines = res_room_line_obj.search(srch_rmline)
                    if rm_lines:
                        rm_line_vals = {'room_id': prod_room.id,
                                        'check_in': chkin,
                                        'check_out': chkout,
                                        'reservation_id': self.folio_id.reservation_id.id,
                                        'status': status}
                        rm_lines.write(rm_line_vals)
                        old_prod_room.write({'isroom': True})
                        prod_room.write({'isroom': False})
                ###########################################################

        return super(HotelFolioLine, self).write(vals)

    @api.multi
    def unlink(self):
        sale_line_obj = self.env['sale.order.line']
        fr_obj = self.env['folio.room.line']
        rrl_obj = self.env['hotel.room.reservation.line']

        for line in self:
            if line.order_line_id:
                sale_unlink_obj = (sale_line_obj.browse
                                   ([line.order_line_id.id]))
                for rec in sale_unlink_obj:
                    room_obj = self.env['hotel.room'
                    ].search([('name', '=', rec.name)])
                    if room_obj.id and not line.is_reserved:
                        folio_arg = [('folio_id', '=', line.folio_id.id),
                                     ('room_id', '=', room_obj.id),
                                     ('check_in', '=', line.checkin_date),
                                     ('check_out', '=', line.checkout_date)]
                        folio_room_line_myobj = fr_obj.search(folio_arg)
                        if folio_room_line_myobj:
                            folio_room_line_myobj.unlink()
                            room_obj.write({'isroom': True,
                                            'status': 'available'})
                    else:
                        res_room_line_arg = [('reservation_id', '=', line.reservation_id.id),
                                             ('room_id', '=', room_obj.id),
                                             ('check_in', '=', line.checkin_date),
                                             ('check_out', '=', line.checkout_date)]
                        res_room_line_myobj = rrl_obj.search(res_room_line_arg)
                        if res_room_line_myobj:
                            res_room_line_myobj.unlink()
                            room_obj.write({'isroom': True,
                                            'status': 'available'})
                sale_unlink_obj.unlink()
        return super(HotelFolioLine, self).unlink()

    @api.multi
    def uos_change(self, product_uos, product_uos_qty=0, product_id=None):
        '''
        @param self: object pointer
        '''
        for folio in self:
            line = folio.order_line_id
            x = line.uos_change(product_uos, product_uos_qty=0,
                                product_id=None)
        return x

    @api.onchange('room_no')
    def compute_price_list(self):
        folio_id = self.folio_id
        price_list_id = folio_id.pricelist_id
        for item in price_list_id.version_id.items_id:
            if item.categ_id.name == self.room_no.categ_id.name:
                self.price_unit = self.room_no.list_price + item.price_surcharge

        folio_id.room_lines.product_uom = self.room_no.uos_id
        folio_id.room_lines.name = self.room_no.name

    # @api.multi
    # def product_id_change(self, pricelist, product, qty=0, uom=False,
    #                       qty_uos=0, uos=False, name='', partner_id=False,
    #                       lang=False, update_tax=True, date_order=False):
    #     '''
    #     @param self: object pointer
    #     '''
    #     line_ids = [folio.order_line_id.id for folio in self]
    #     if product:
    #         sale_line_obj = self.env['sale.order.line'].browse(line_ids)
    #         return sale_line_obj.product_id_change(pricelist, product, qty=0,
    #                                                uom=uom, qty_uos=0,
    #                                                uos=uos, name='',
    #                                                partner_id=partner_id,
    #                                                lang=False,
    #                                                update_tax=True,
    #                                                date_order=False)
    #
    #
    #
    #
    # @api.multi
    # def product_uom_change(self, pricelist, product, qty=0,
    #                        uom=False, qty_uos=0, uos=False, name='',
    #                        partner_id=False, lang=False, update_tax=True,
    #                        date_order=False):
    #     '''
    #     @param self: object pointer
    #     '''
    #
    #     if product:
    #         return self.product_id_change(pricelist, product, qty=0,
    #                                       uom=uom, qty_uos=0, uos=uos,
    #                                       name='', partner_id=partner_id,
    #                                       lang=False, update_tax=True,
    #                                       date_order=False)

    @api.constrains('checkin_date', 'checkout_date')
    def check_dates(self):
        '''
        This method is used to validate the checkin_date and checkout_date.
        -------------------------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        if self.checkin_date and self.checkout_date:
            if self.checkin_date >= self.checkout_date:
                raise ValidationError(_('Check in Date Should be \
                less than the Check Out Date!'))
        if self.folio_id.date_order and self.checkin_date:
            if self.checkin_date <= self.folio_id.date_order:
                raise ValidationError(_('Check in date should be \
                greater than the current date.'))

    @api.onchange('checkin_date', 'checkout_date')
    def on_change_checkout(self):
        '''
        When you change checkin_date or checkout_date it will checked it
        and update the qty of hotel folio line
        -----------------------------------------------------------------
        @param self: object pointer
        '''
        if not self.checkin_date:
            self.checkin_date = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        if not self.checkout_date:
            self.checkout_date = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        chckin = self.checkin_date
        chckout = self.checkout_date
        if chckin and chckout:
            server_dt = DEFAULT_SERVER_DATETIME_FORMAT
            chkin_dt = datetime.datetime.strptime(chckin, server_dt)
            chkout_dt = datetime.datetime.strptime(chckout, server_dt)
            dur = chkout_dt - chkin_dt
            sec_dur = dur.seconds
            if (not dur.days and not sec_dur) or (dur.days and not sec_dur):
                myduration = dur.days
            else:
                myduration = dur.days + 1
        self.product_uom_qty = myduration

    @api.multi
    def button_confirm(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            line = folio.order_line_id
            x = line.button_confirm()
        return x

    @api.multi
    def button_done(self):
        '''
        @param self: object pointer
        '''
        line_ids = [folio.order_line_id.id for folio in self]
        sale_line_obj = self.env['sale.order.line'].browse(line_ids)
        sale_line_obj.button_done()
        res = self.write({'state': 'done'})
        for line in self:
            workflow.trg_write(self._uid, 'sale.order',
                               line.order_line_id.order_id.id, self._cr)
        return res


#    @api.one
#    def copy_data(self, default=None):
#        '''
#        @param self: object pointer
#        @param default: dict of default values to be set
#        '''
#        line_id = self.order_line_id.id
#        sale_line_obj = self.env['sale.order.line'].browse(line_id)
#        return sale_line_obj.copy_data(default=default)


class HotelServiceLine(models.Model):

    @api.multi
    def _amount_line(self, field_name, arg):
        '''
        @param self: object pointer
        @param field_name: Names of fields.
        @param arg: User defined arguments
        '''
        for folio in self:
            line = folio.service_line_id
            x = line._amount_line(field_name, arg)
        return x

    @api.multi
    def _number_packages(self, field_name, arg):
        '''
        @param self: object pointer
        @param field_name: Names of fields.
        @param arg: User defined arguments
        '''
        for folio in self:
            line = folio.service_line_id
            x = line._number_packages(field_name, arg)
        return x

    @api.model
    def _service_checkin_date(self):
        if 'checkin' in self._context:
            return self._context['checkin']
        return time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    @api.model
    def _service_checkout_date(self):
        if 'checkout' in self._context:
            return self._context['checkout']
        return time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    _name = 'hotel.service.line'
    _description = 'hotel Service line'

    service_line_id = fields.Many2one('sale.order.line', 'Service Line',
                                      required=True, delegate=True,
                                      ondelete='cascade')
    folio_id = fields.Many2one('hotel.folio', 'Folio', ondelete='cascade')
    ser_checkin_date = fields.Datetime('From Date', required=True,
                                       default=_service_checkin_date)
    ser_checkout_date = fields.Datetime('To Date', required=True,
                                        default=_service_checkout_date)

    @api.model
    def create(self, vals, check=True):
        """
        Overrides orm create method.
        @param self: The object pointer
        @param vals: dictionary of fields value.
        @return: new record set for hotel service line.
        """
        if 'folio_id' in vals:
            folio = self.env['hotel.folio'].browse(vals['folio_id'])
            vals.update({'order_id': folio.order_id.id})
        return super(models.Model, self).create(vals)

    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        s_line_obj = self.env['sale.order.line']
        for line in self:
            if line.service_line_id:
                sale_unlink_obj = s_line_obj.browse([line.service_line_id.id])
                sale_unlink_obj.unlink()
        return super(HotelServiceLine, self).unlink()

    @api.multi
    def product_id_change(self, pricelist, product, qty=0,
                          uom=False, qty_uos=0, uos=False, name='',
                          partner_id=False, lang=False, update_tax=True,
                          date_order=False):
        '''
        @param self: object pointer
        '''
        line_ids = [folio.service_line_id.id for folio in self]
        if product:
            sale_line_obj = self.env['sale.order.line'].browse(line_ids)
            return sale_line_obj.product_id_change(pricelist, product, qty=0,
                                                   uom=uom, qty_uos=0,
                                                   uos=uos, name='',
                                                   partner_id=partner_id,
                                                   lang=False,
                                                   update_tax=True,
                                                   date_order=False)

    @api.multi
    def product_uom_change(self, pricelist, product, qty=0,
                           uom=False, qty_uos=0, uos=False, name='',
                           partner_id=False, lang=False, update_tax=True,
                           date_order=False):
        '''
        @param self: object pointer
        '''
        if product:
            return self.product_id_change(pricelist, product, qty=0,
                                          uom=uom, qty_uos=0, uos=uos,
                                          name='', partner_id=partner_id,
                                          lang=False, update_tax=True,
                                          date_order=False)

    @api.onchange('ser_checkin_date', 'ser_checkout_date')
    def on_change_checkout(self):
        '''
        When you change checkin_date or checkout_date it will checked it
        and update the qty of hotel service line
        -----------------------------------------------------------------
        @param self: object pointer
        '''
        if not self.ser_checkin_date:
            time_a = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            self.ser_checkin_date = time_a
        if not self.ser_checkout_date:
            self.ser_checkout_date = time_a
        if self.ser_checkout_date < self.ser_checkin_date:
            raise UserError(_('Checkout must be greater or equal checkin\
                               date'))
        if self.ser_checkin_date and self.ser_checkout_date:
            date_a = time.strptime(self.ser_checkout_date,
                                   DEFAULT_SERVER_DATETIME_FORMAT)[:5]
            date_b = time.strptime(self.ser_checkin_date,
                                   DEFAULT_SERVER_DATETIME_FORMAT)[:5]
            diffDate = datetime.datetime(*date_a) - datetime.datetime(*date_b)
            qty = diffDate.days + 1
            self.product_uom_qty = qty

    @api.multi
    def button_confirm(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            line = folio.service_line_id
            x = line.button_confirm()
        return x

    @api.multi
    def button_done(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            line = folio.service_line_id
            x = line.button_done()
        return x


#    @api.one
#    def copy_data(self, default=None):
#        '''
#        @param self: object pointer
#        @param default: dict of default values to be set
#        '''
#        sale_line_obj = self.env['sale.order.line'
#                                 ].browse(self.service_line_id.id)
#        return sale_line_obj.copy_data(default=default)


###########################################################
# Sophanon Nun, adding service line to Hotel Folio


class ReservationServiceLine(models.Model):
    _name = 'hotel.restaurant.line'

    _description = 'Hotel Restaurant Line'

    restaurant_line_id = fields.Many2one('hotel.folio')
    product_id = fields.Many2one('hotel.services')
    price_subtotal = fields.Float('Subtotal', readonly=True)
    product_uom_qty = fields.Float('Quantity', default=1)
    list_price = fields.Float('Price Unit')
    name = fields.Char('Description')
    uom_id = fields.Many2one('product.uom', 'UoM')
    restaurant_line_tax_id = fields.Many2many('account.tax',
                                              'account_invoice_line_tax', 'invoice_line_id', 'tax_id',
                                              string='Taxes',
                                              domain=[('parent_id', '=', False), '|', ('active', '=', False),
                                                      ('active', '=', True)])

    @api.onchange('product_id')
    def onchange_product_id(self):
        product_id = self.product_id
        self.uom_id = product_id.uom_id
        self.name = product_id.name
        self.list_price = product_id.list_price
        self.restaurant_line_tax_id = [(6, 0, [x.id for x in product_id.taxes_id])]

    @api.constrains('product_uom_qty', 'list_price')
    def subtotal(self):
        self.price_subtotal = self.product_uom_qty * self.list_price
        if self.restaurant_line_tax_id:
            tax = 1.0
            for t in self.restaurant_line_tax_id:
                tax = tax + t.amount
            self.price_subtotal = self.price_subtotal * tax


class HotelServiceType(models.Model):
    _name = "hotel.service.type"
    _description = "Service Type"

    ser_id = fields.Many2one('product.category', 'category', required=True,
                             delegate=True, select=True, ondelete='cascade')


class HotelServices(models.Model):
    _name = 'hotel.services'
    _description = 'Hotel Services and its charges'

    service_id = fields.Many2one('product.product', 'Service_id',
                                 required=True, ondelete='cascade',
                                 delegate=True)


class ResCompany(models.Model):
    _inherit = 'res.company'

    additional_hours = fields.Integer('Additional Hours',
                                      help="Provide the min hours value for \
check in, checkout days, whatever the hours will be provided here based \
on that extra days will be calculated.")


class CurrencyExchangeRate(models.Model):
    _name = "currency.exchange"
    _description = "currency"

    name = fields.Char('Reg Number', readonly=True)
    today_date = fields.Datetime('Date Ordered',
                                 required=True,
                                 default=(lambda *a:
                                          time.strftime
                                          (DEFAULT_SERVER_DATETIME_FORMAT)))
    input_curr = fields.Many2one('res.currency', string='Input Currency',
                                 track_visibility='always')
    in_amount = fields.Float('Amount Taken', size=64, default=1.0)
    out_curr = fields.Many2one('res.currency', string='Output Currency',
                               track_visibility='always')
    out_amount = fields.Float('Subtotal', size=64)
    folio_no = fields.Many2one('hotel.folio', 'Folio Number')
    guest_name = fields.Many2one('res.partner', string='Guest Name')
    room_number = fields.Char(string='Room Number')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'),
                              ('cancel', 'Cancel')], 'State', default='draft')
    rate = fields.Float('Rate(per unit)', size=64)
    hotel_id = fields.Many2one('stock.warehouse', 'Hotel Name')
    type = fields.Selection([('cash', 'Cash')], 'Type', default='cash')
    tax = fields.Selection([('2', '2%'), ('5', '5%'), ('10', '10%')],
                           'Service Tax', default='2')
    total = fields.Float('Amount Given')

    @api.model
    def create(self, vals):
        """
        Overrides orm create method.
        @param self: The object pointer
        @param vals: dictionary of fields value.
        """
        if not vals:
            vals = {}
        if self._context is None:
            self._context = {}
        vals['name'] = self.env['ir.sequence'].get('currency.exchange')
        return super(CurrencyExchangeRate, self).create(vals)

    @api.onchange('folio_no')
    def get_folio_no(self):
        '''
        When you change folio_no, based on that it will update
        the guest_name,hotel_id and room_number as well
        ---------------------------------------------------------
        @param self: object pointer
        '''
        for rec in self:
            self.guest_name = False
            self.hotel_id = False
            self.room_number = False
            if rec.folio_no and len(rec.folio_no.room_lines) != 0:
                self.guest_name = rec.folio_no.partner_id.id
                self.hotel_id = rec.folio_no.warehouse_id.id
                self.room_number = rec.folio_no.room_lines[0].room_no.name

    @api.multi
    def act_cur_done(self):
        """
        This method is used to change the state
        to done of the currency exchange
        ---------------------------------------
        @param self: object pointer
        """
        self.write({'state': 'done'})
        return True

    @api.multi
    def act_cur_cancel(self):
        """
        This method is used to change the state
        to cancel of the currency exchange
        ---------------------------------------
        @param self: object pointer
        """
        self.write({'state': 'cancel'})
        return True

    @api.multi
    def act_cur_cancel_draft(self):
        """
        This method is used to change the state
        to draft of the currency exchange
        ---------------------------------------
        @param self: object pointer
        """
        self.write({'state': 'draft'})
        return True

    @api.model
    def get_rate(self, a, b):

        try:
            url = 'https://api.fixer.io/latest?base=%s' % (a)
            response = urllib2.urlopen(url).read().rstrip()
            data = json.loads(response)
            rates = data['rates']
            if b in rates:
                rate_per_unit = rates[b]
                return Decimal(rate_per_unit)
            else:
                return Decimal(0)
        except:
            return Decimal('-1.00')

    @api.onchange('input_curr', 'out_curr', 'in_amount')
    def get_currency(self):
        self.out_amount = 0.0
        if self.input_curr:
            for rec in self:
                result = rec.get_rate(self.input_curr.name,
                                      self.out_curr.name)
                if self.out_curr:
                    self.rate = result
                    if self.rate == Decimal('-1.00'):
                        raise except_orm(_('Warning'),
                                         _('Please Check Your \
                                             Network Connectivity.'))
                    elif self.rate == 0:
                        raise except_orm(_('Warning'),
                                         _('We can not find rate per unit for %s Please manually input' % (
                                             self.out_curr.name)))
                    self.out_amount = (float(result) * float(self.in_amount))

    @api.onchange('out_amount', 'tax')
    def tax_change(self):
        '''
        When you change out_amount or tax
        it will update the total of the currency exchange
        -------------------------------------------------
        @param self: object pointer
        '''
        if self.out_amount:
            for rec in self:
                ser_tax = ((rec.out_amount) * (float(rec.tax))) / 100
                rec.total = rec.out_amount - ser_tax

# class AccountInvoice(models.Model):

#     _inherit = 'account.invoice'

#     @api.multi
#     def confirm_paid(self):
#         '''
#         This method change pos orders states to done when folio invoice
#         is in done.
#         ----------------------------------------------------------
#         @param self: object pointer
#         '''
#         pos_order_obj = self.env['pos.order']
#         res = super(AccountInvoice, self).confirm_paid()
#         pos_ids = pos_order_obj.search([('invoice_id', 'in', self._ids)])
#         if pos_ids.ids:
#             for pos_id in pos_ids:
#                 pos_id.write({'state': 'done'})
#         return res
