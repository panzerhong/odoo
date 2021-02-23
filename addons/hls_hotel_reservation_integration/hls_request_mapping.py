from openerp import models, fields, api, _
from openerp.exceptions import except_orm, ValidationError
import datetime
import logging
import requests
import yaml
import xmltodict, json
import xml.etree.cElementTree as ET
from dateutil.parser import parse
import requests.exceptions
import time

_logger = logging.getLogger(__name__)
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT


class GetBooking(models.Model):
    _name = 'schedulling.getbooking.hls'

    # This function use in case a particular reservation didn't auto check in #######
    @api.model
    def force_create_folio(self):
        hotel_folio_obj = self.env['hotel.folio']
        room_obj = self.env['hotel.room']
        product_obj = self.env['product.product']
        reservation = self.env['hotel.reservation'].browse([1830])
        folio_lines = []
        res_service_lines = []
        checkin_date = reservation['checkin']
        checkout_date = reservation['checkout']
        if not reservation.checkin < reservation.checkout:
            raise except_orm(_('Error'),
                             _('Checkout date should be greater \
                                                than the Checkin date.'))
        duration_vals = (reservation.onchange_check_dates
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
        folio_vals.update(
            {'room_lines': folio_lines, 'service_lines': res_service_lines})
        folio = hotel_folio_obj.create(folio_vals)
        self._cr.execute('insert into hotel_folio_reservation_rel'
                         '(order_id, invoice_id) values (%s,%s)',
                         (reservation.id, folio.id)
                         )
        reservation.write({'state': 'done', 'folio_no': folio.id, 'BookingFromOTA': True})

    #################################################################################
    @api.multi
    def define_room_ids(self):
        room_ids = self.env['hotel.room'].search([('categ_id_2.name', '=', 'Standard'),('categ_id.name','!=','Stop Use')])
        return room_ids

    @api.multi
    def select_available_rooms(self, hls_checkin, hls_checkout, array_type):
        reservation_line = []
        arr_room = []
        room_ids = self.define_room_ids()
        temp = 0
        len_room = len(array_type)
        for r in room_ids:
            available = 1
            for line in r.room_reservation_line_ids:
                line_checkin = parse(line.check_in)
                line_checkout = parse(line.check_out)
                if line.status != "cancel":
                    if (line_checkin <= hls_checkin <= line_checkout) or (
                            line_checkin <= hls_checkout <= line_checkout) or (
                            hls_checkin < line_checkin and hls_checkout > line_checkout):
                        available = 0
                        break
            for line in r.room_line_ids:
                line_checkin = parse(line.check_in)
                line_checkout = parse(line.check_out)
                if line.status != "cancel":
                    if (hls_checkin >= line_checkin and hls_checkin <= line_checkout) or (
                            hls_checkout >= line_checkin and hls_checkout <= line_checkout) or (
                            hls_checkin < line_checkin and hls_checkout > line_checkout):
                        available = 0
                        break
            if available == 1:
                if temp < len_room:
                    arr_room.append(r.id)
                    temp = temp + 1
                else:
                    break
        if len(arr_room):
            reservation_line.append(
                [0, False, {'categ_id': 1, 'name': False, 'reserve': [[6, False, arr_room]]}])
        return reservation_line

    # @api.model
    # def request_to_hls(self):
    #     hls_booking = dict()
    #     _logger.info('request_to_hls======>')
    #     GetBooking = """
    #         <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:soap="https://api.hotellinksolutions.com/services/booking/soap">
    #         <soapenv:Header/>
    #         <soapenv:Body>
    #         <soap:GetBookings>
    #         <Request>
    #         <StartDate></StartDate>
    #         <EndDate></EndDate>
    #         <DateFilter>LastModifiedDate</DateFilter>
    #         <BookingStatus></BookingStatus>
    #         <BookingId></BookingId>
    #         <ExtBookingRef></ExtBookingRef>
    #         <NumberBookings></NumberBookings>
    #         <Credential>
    #             <ChannelManagerUsername>tokyo</ChannelManagerUsername> 
    #             <ChannelManagerPassword>!?Hh7AC^v,*9uPd</ChannelManagerPassword> 
    #             <HotelId>93d2c493-35fa-1519615468-4b37-b5bb-181e59dbe9de</HotelId> 
    #             <HotelAuthenticationChannelKey>0f62852c65b34cbc19eb29d354936a0f</HotelAuthenticationChannelKey> 
    #         </Credential>
    #         <Language>en</Language>
    #         </Request>
    #         </soap:GetBookings>
    #         </soapenv:Body>
    #         </soapenv:Envelope>
    #         """
    #     ReadNotification = """
    #         <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:soap="https://api.hotellinksolutions.com/services/booking/soap" xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/">
    #             <soapenv:Header/>
    #             <soapenv:Body>
    #                 <soap:ReadNotification>
    #                     <Request>
    #                     <Bookings>
    #                     </Bookings>
    #                     <Credential>
    #                         <ChannelManagerUsername>tokyo</ChannelManagerUsername> 
    #                         <ChannelManagerPassword>!?Hh7AC^v,*9uPd</ChannelManagerPassword> 
    #                         <HotelId>93d2c493-35fa-1519615468-4b37-b5bb-181e59dbe9de</HotelId> 
    #                         <HotelAuthenticationChannelKey>0f62852c65b34cbc19eb29d354936a0f</HotelAuthenticationChannelKey> 
    #                     </Credential>
    #                     <Language>en</Language>
    #                     </Request>
    #                 </soap:ReadNotification>
    #             </soapenv:Body>
    #         </soapenv:Envelope>
    #         """

    #     today = datetime.date.today()
    #     body_req = ET.fromstring(GetBooking)
    #     for statDate in body_req.getiterator('StartDate'):
    #         statDate.text = str(today)
    #         # statDate.text = '2018-06-10'
    #     for endDate in body_req.getiterator('EndDate'):
    #         endDate.text = str(today)
    #         # endDate.text = '2018-06-10'
    #     xmlstr = ET.tostring(body_req, encoding='utf8', method='xml')
    #     headers = {"Content-Type": "application/xml"}  # set what your serve-r accepts

    #     try:
    #         response = requests.post("https://api.hotellinksolutions.com/services/booking/soap", data=xmlstr,
    #                                  headers=headers)
    #         str_xml = xmltodict.parse(response.content)
    #         str_json = json.dumps(str_xml)
    #         booking_hls = yaml.load(str_json)

    #         if booking_hls['SOAP-ENV:Envelope']['SOAP-ENV:Body']['ns1:GetBookingsResponse']['GetBookingsResult'][
    #             'Bookings'] is None:
    #             _logger.info("No Booking Transaction")
    #         else:
    #             booking_resp = \
    #                 booking_hls['SOAP-ENV:Envelope']['SOAP-ENV:Body']['ns1:GetBookingsResponse']['GetBookingsResult'][
    #                     'Bookings']['ns1:Booking']

    #             ### update data to hls_booking dictionary ###########################
    #             else_data = dict()
    #             dict_ids = ""
    #             else_case = "False"
    #             for booking in booking_resp:
    #                 if type(booking) == dict:
    #                     booking_id = booking['BookingId']
    #                     data = dict()
    #                     for val in booking:
    #                         if val == 'BookingId':
    #                             continue
    #                         data.update({val: booking[val]})
    #                         hls_booking.update({booking_id: data})
    #                 else:
    #                     else_case = "True"
    #                     if booking == "BookingId":
    #                         dict_ids = booking_resp[booking]
    #                     else:
    #                         else_data.update({booking: booking_resp[booking]})
    #             if else_case == "True":
    #                 hls_booking.update({dict_ids: else_data})
    #             #####################################################################

    #             reservation_obj = self.env['hotel.reservation']
    #             room_reservation_line_obj = self.env['hotel.room.reservation.line']
    #             hotel_reservation_line_obj = self.env['hotel_reservation.line']
    #             element_notification = ET.fromstring(ReadNotification)
    #             read_notification = False

    #             for hls_id in hls_booking:
    #                 if "PM" not in hls_id:
    #                     ### add item ReadNotification ################################
    #                     for request in element_notification.getiterator('Request'):
    #                         for data in request:
    #                             if data.tag == "Bookings":
    #                                 item_element = ET.fromstring("<item></item>")
    #                                 data.append(item_element)
    #                                 for item in data:
    #                                     if item.text == None:
    #                                         item.text = hls_id
    #                                 break
    #                     ##############################################################
    #                     booking_status = ""
    #                     if hls_booking[hls_id]['BookingStatus'] == "Confirmed":
    #                         booking_status = "confirm"
    #                     elif hls_booking[hls_id]['BookingStatus'] == "Operational":
    #                         booking_status = "done"
    #                     elif hls_booking[hls_id]['BookingStatus'] == "Cancelled":
    #                         booking_status = "cancel"
    #                     elif hls_booking[hls_id]['BookingStatus'] == "Completed":
    #                         _logger.info("HLS COMPLETED")
    #                         continue

    #                     hotel_reservation_id = reservation_obj.search([('booking_id', '=', hls_id)])
    #                     if hotel_reservation_id.id:
    #                         if hotel_reservation_id.state != booking_status:
    #                             if booking_status == "cancel":
    #                                 hotel_reservation_id.write({'state': 'cancel', 'BookingFromOTA': True})
    #                                 room_reservation_line = room_reservation_line_obj.search([('reservation_id',
    #                                                                                            'in',
    #                                                                                            hotel_reservation_id.ids)])
    #                                 room_reservation_line.unlink()
    #                                 read_notification = True
    #                             elif booking_status == "done":
    #                                 hotel_reservation_id._create_folio()
    #                         else:
    #                             if booking_status == "confirm":
    #                                 guest = {
    #                                     'name': hls_booking[hls_id]['Guests']['FirstName'],
    #                                     'last_name': hls_booking[hls_id]['Guests']['LastName'],
    #                                     'email': hls_booking[hls_id]['Guests']['Email'],
    #                                     'phone': hls_booking[hls_id]['Guests']['Phone'],
    #                                     'city': hls_booking[hls_id]['Guests']['City'],
    #                                     'zip': hls_booking[hls_id]['Guests']['PostalCode'],
    #                                 }
    #                                 hotel_reservation_id.partner_id.write(guest)
    #                                 hls_checkin = parse(hls_booking[hls_id]["CheckIn"] + "T07:00:00")
    #                                 hls_checkout = parse(hls_booking[hls_id]["CheckOut"] + "T05:00:00")

    #                                 for booking_item in hls_booking[hls_id]["Rooms"]:
    #                                     odoo_room_type_id = []
    #                                     hls_roomId = []

    #                                     for arr_room in hls_booking[hls_id]["Rooms"][booking_item]:
    #                                         if type(arr_room) != dict:
    #                                             if hls_booking[hls_id]["Rooms"][booking_item][
    #                                                 "BookingItemStatus"] != "Cancelled":
    #                                                 hls_roomId.append(
    #                                                     hls_booking[hls_id]["Rooms"][booking_item]["RoomId"])
    #                                                 break
    #                                         else:
    #                                             hls_roomId.append(arr_room["RoomId"])
    #                                     for reservation_line in hotel_reservation_id.reservation_line:
    #                                         for room in reservation_line.reserve:
    #                                             odoo_room_type_id.append(room.room_type_id)

    #                                     # Define deleteID & addID #######################################
    #                                     check_id = []
    #                                     deleteId = []
    #                                     addId = []
    #                                     for reservation_line in hotel_reservation_id.reservation_line:
    #                                         for room in reservation_line.reserve:
    #                                             RoomTypeID = room.room_type_id
    #                                             if RoomTypeID not in check_id:
    #                                                 odoo_count = odoo_room_type_id.count(RoomTypeID)
    #                                                 hls_count = hls_roomId.count(RoomTypeID)
    #                                                 rang = odoo_count - hls_count
    #                                                 if rang > 0:
    #                                                     for r in reservation_line.reserve:
    #                                                         if r.room_type_id == RoomTypeID:
    #                                                             if rang == 0:
    #                                                                 break
    #                                                             else:
    #                                                                 deleteId.append(room.id)
    #                                                                 rang = rang - 1
    #                                                 elif rang < 0:
    #                                                     while (rang < 0):
    #                                                         addId.append(RoomTypeID)
    #                                                         rang = rang + 1
    #                                                 check_id.append(RoomTypeID)
    #                                     #################################################################

    #                                     # delete room lines based on deleteID ##########################################
    #                                     line_ids = room_reservation_line_obj.search(
    #                                         [('reservation_id.id', '=', hotel_reservation_id.id)])
    #                                     for line in line_ids:
    #                                         if line.room_id.id in deleteId:
    #                                             line.unlink()
    #                                     hr_line_ids = hotel_reservation_line_obj.search(
    #                                         [('line_id', '=', hotel_reservation_id.id)])
    #                                     for line_type in hr_line_ids:
    #                                         # we use raw query because we want to delete line many2many relationship ###
    #                                         for room in line_type.reserve:
    #                                             if room.id in deleteId:
    #                                                 reservation_line_id = line_type.id
    #                                                 roomId = room.id
    #                                                 self._cr.execute(
    #                                                     "delete from hotel_reservation_line_room_rel where (hotel_reservation_line_id=%s and room_id=%s)",
    #                                                     (reservation_line_id, roomId))
    #                                     ################################################################################

    #                                     if len(addId):
    #                                         room_ids = self.define_room_ids()
    #                                         for i in addId:
    #                                             for r in room_ids:
    #                                                 available = 1
    #                                                 for line in r.room_reservation_line_ids:
    #                                                     line_checkin = parse(line.check_in)
    #                                                     line_checkout = parse(line.check_out)
    #                                                     if line.status != "cancel":
    #                                                         if (
    #                                                                 line_checkin <= hls_checkin <= line_checkout) or (
    #                                                                 line_checkin <= hls_checkout <= line_checkout) or (
    #                                                                 hls_checkin < line_checkin and hls_checkout > line_checkout):
    #                                                             available = 0
    #                                                             break
    #                                                 for line in r.room_line_ids:
    #                                                     line_checkin = parse(line.check_in)
    #                                                     line_checkout = parse(line.check_out)
    #                                                     if line.status != "cancel":
    #                                                         if (
    #                                                                 line_checkin <= hls_checkin <= line_checkout) or (
    #                                                                 line_checkin <= hls_checkout <= line_checkout) or (
    #                                                                 hls_checkin < line_checkin and hls_checkout > line_checkout):
    #                                                             available = 0
    #                                                             break
    #                                                 if available == 1:
    #                                                     vals = {
    #                                                         'line_id': hotel_reservation_id.id,
    #                                                         'categ_id': r.categ_id.id,
    #                                                         'name': False,
    #                                                         'reserve': [[6, False, [r.id]]]}
    #                                                     hotel_reservation_line_obj.create(vals)
    #                                                     vals = {
    #                                                         'room_id': r.id,
    #                                                         'reservation_id': hotel_reservation_id.id,
    #                                                         'check_in': hotel_reservation_id.checkin,
    #                                                         'check_out': hotel_reservation_id.checkout,
    #                                                         'state': 'assigned',
    #                                                     }
    #                                                     room_reservation_line_obj.create(vals)
    #                                                     break

    #                                 read_notification = True

    #                     else:
    #                         read_notification = self.create_reservation(hls_booking, hls_id)

    #             if read_notification:
    #                 try:
    #                     notification_str = ET.tostring(element_notification)
    #                     _logger.info("ReadNotification Request ====>")
    #                     # inform_to_hls = requests.post("https://api.hotellinksolutions.com/services/booking/soap",
    #                     #                               data=notification_str,
    #                     #                               headers=headers)
    #                     # _logger.info(inform_to_hls.text)
    #                 except requests.exceptions.ConnectionError as e:
    #                     _logger.info(e)
    #             return True
    #     except requests.exceptions.ConnectionError as e:
    #         _logger.info(e)

    # @api.multi
    # def create_reservation(self, hls_booking, hls_id):
    #     partner_obj = self.env['res.partner']
    #     room_reservation_line_obj = self.env['hotel.room.reservation.line']
    #     reservation_obj = self.env['hotel.reservation']
    #     array_type = []
    #     booking_data = hls_booking[hls_id]
    #     if booking_data['BookingStatus'] == "Cancelled":
    #         return True
    #     else:
    #         try:
    #             date_orderd = booking_data['BookingDate']
    #             checkIn = booking_data['CheckIn'] + "T07:00:00"
    #             checkOut = booking_data['CheckOut'] + "T05:00:00"
    #             for booking_items in booking_data['Rooms']:
    #                 for arr_room in booking_data['Rooms'][booking_items]:
    #                     if type(arr_room) == dict:
    #                         for each_room_data in arr_room:
    #                             if each_room_data == "RoomId":
    #                                 array_type.append(arr_room[each_room_data])
    #                     else:
    #                         if arr_room == "RoomId":
    #                             array_type.append(booking_data['Rooms'][booking_items][arr_room])
    #             guest = {
    #                 'name': booking_data['Guests']['FirstName'],
    #                 'last_name': booking_data['Guests']['LastName'],
    #                 'email': booking_data['Guests']['Email'],
    #                 'phone': booking_data['Guests']['Phone'],
    #                 'city': booking_data['Guests']['City'],
    #                 'zip': booking_data['Guests']['PostalCode'],
    #             }
    #             hls_checkin = parse(checkIn)
    #             hls_checkout = parse(checkOut)
    #             reservation_line = self.select_available_rooms(hls_checkin, hls_checkout, array_type)
    #             partner_ids = 0
    #             if guest['email']:
    #                 partner_ids = partner_obj.search([('email', '=', guest['email'])])
    #             if partner_ids.id:
    #                 partner_id = partner_ids.id
    #             else:
    #                 partner_id = partner_obj.create(guest).id
    #             vals = {
    #                 'date_order': date_orderd,
    #                 'checkin': checkIn,
    #                 'checkout': checkOut,
    #                 'warehouse_id': 1,
    #                 'booking_id': hls_id,
    #                 'partner_id': partner_id,
    #                 'partner_shipping_id': partner_id,
    #                 'partner_order_id': partner_id,
    #                 'partner_invoice_id': partner_id,
    #                 'pricelist_id': 11,
    #                 'reservation_line': reservation_line
    #             }
    #             reservation_id = reservation_obj.create(vals)
    #             self._cr.execute("select count(*) from hotel_reservation as hr "
    #                              "inner join hotel_reservation_line as hrl on \
    #                              hrl.line_id = hr.id "
    #                              "inner join hotel_reservation_line_room_rel as \
    #                              hrlrr on hrlrr.room_id = hrl.id "
    #                              "where (checkin,checkout) overlaps \
    #                              ( timestamp %s, timestamp %s ) "
    #                              "and hr.id <> cast(%s as integer) "
    #                              "and hr.state = 'confirm' "
    #                              "and hrlrr.hotel_reservation_line_id in ("
    #                              "select hrlrr.hotel_reservation_line_id \
    #                              from hotel_reservation as hr "
    #                              "inner join hotel_reservation_line as \
    #                              hrl on hrl.line_id = hr.id "
    #                              "inner join hotel_reservation_line_room_rel \
    #                              as hrlrr on hrlrr.room_id = hrl.id "
    #                              "where hr.id = cast(%s as integer) )",
    #                              (reservation_id.checkin, reservation_id.checkout,
    #                               str(reservation_id.id), str(reservation_id.id)))
    #             res = self._cr.fetchone()
    #             roomcount = res and res[0] or 0.0
    #             if roomcount:
    #                 raise except_orm(_('Warning'), _('You tried to confirm \
    #                                             reservation with room those already reserved in this \
    #                                             reservation period'))
    #             else:
    #                 reservation_id.write({'state': 'confirm'})
    #                 for line_id in reservation_id.reservation_line:
    #                     line_id = line_id.reserve
    #                     for room_id in line_id:
    #                         vals = {
    #                             'room_id': room_id.id,
    #                             'reservation_id': reservation_id.id,
    #                             'check_in': reservation_id.checkin,
    #                             'check_out': reservation_id.checkout,
    #                             'state': 'assigned',
    #                         }
    #                         room_reservation_line_obj.create(vals)
    #             vals.clear()
    #             return True
    #         except:
    #             raise except_orm(_('Warning'), _('Exception occurred while creating Reservation!!!'))

class confirm_wizard(models.TransientModel):
    _name = 'hotel.confirm_wizard'

    reservation_id = fields.Many2one('hotel.reservation',"Reservation")

    @api.multi
    def confirm(self):
        context = self._context
        if context['active_model'] == 'hotel.reservation':
            self.reservation_id = context['active_id']
        self.reservation_id.signal_workflow('cancel')

class save_booking(models.Model):
    _inherit = 'hotel.reservation'
    booking_id = fields.Char('HLS Reference', readonly=True)
    pick_up = fields.Boolean('Pick-Up')
    drop_off = fields.Boolean('Drop-Off')
    flight_inbound = fields.Char('Flight Inbound')
    flight_outbound = fields.Char('Flight Outbound')

    @api.multi
    def return_confirmation(self):
        return {
            'name': 'Are you sure?',
            'type': 'ir.actions.act_window',
            'res_model': 'hotel.confirm_wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
        }

    # Helper functions #############################
    @api.multi
    def define_room_types(self):
        room_types = {}
        for lines in self.reservation_line:
            for room in lines.reserve:
                if room.categ_id.name == "Standard":
                    if room.room_type_id not in room_types:
                        room_types.update({room.categ_id.id: True})
        return room_types

    @api.multi
    def define_notifybooking(self):
        NotifyBooking = """
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:soap="https://api.hotellinksolutions.com/services/booking/soap" xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/">
            <soapenv:Header/>
            <soapenv:Body>
            <soap:NotifyBookings>
            <Request>
            <Bookings>
                <Booking>
                <NotificationType>New</NotificationType>
                <BookingId></BookingId>
                <ExtBookingRef>test-ext-ref</ExtBookingRef>
                <Currency>USD</Currency>
                <CheckIn></CheckIn>
                <CheckOut></CheckOut>
                <AdditionalComments></AdditionalComments>
                <GuestDetail>
                <Title>Mr</Title>
                <FirstName></FirstName>
                <LastName></LastName>
                <Email></Email>
                <Phone></Phone>
                <Address></Address>
                <City></City>
                <State></State>
                <Country></Country>
                <PostalCode></PostalCode>
                </GuestDetail>
                <Rooms>
                <BookingItem>
                <RatePlanId></RatePlanId>
                <Adults></Adults>
                <Children></Children>
                <ExtraAdults></ExtraAdults>
                <ExtraChildren></ExtraChildren>
                <TaxFee></TaxFee>
                <TaxFeeArrival></TaxFeeArrival>
                <Discount></Discount>
                <Deposit></Deposit>
                <Amount></Amount>
                </BookingItem>
                </Rooms>
                <ServiceCharge></ServiceCharge>
                <ServiceChargeArrival></ServiceChargeArrival>
                </Booking>
                </Bookings>
                <Credential>
                <ChannelManagerUsername>tokyo</ChannelManagerUsername> 
                <ChannelManagerPassword>!?Hh7AC^v,*9uPd</ChannelManagerPassword> 
                <HotelId>93d2c493-35fa-1519615468-4b37-b5bb-181e59dbe9de</HotelId> 
                <HotelAuthenticationChannelKey>0f62852c65b34cbc19eb29d354936a0f</HotelAuthenticationChannelKey> 
                </Credential>
                <Language>en</Language>
                </Request>
                </soap:NotifyBookings>
               </soapenv:Body>
            </soapenv:Envelope>
        """
        xmlstr = ET.fromstring(NotifyBooking)

        price_list_items = self.pricelist_id.version_id.items_id
        reservation_line = self.reservation_line
        hotel_room_obj = self.env['hotel.room']
        sale_price = []
        array_room_id = []

        server_dt = DEFAULT_SERVER_DATETIME_FORMAT
        checkin = datetime.datetime.strptime(self.checkin, server_dt)
        checkout = datetime.datetime.strptime(self.checkout, server_dt)
        duration = checkout - checkin + datetime.timedelta(days=1)

        for lines in reservation_line:
            for room in lines.reserve:
                if room.categ_id_2.name == "Standard":
                    for items_id in price_list_items:
                        if items_id.categ_id.name == room.categ_id.name:
                            sale_price.append(
                                (1 + items_id.price_discount) * room.list_price + items_id.price_surcharge)
                        elif not items_id.categ_id:
                            sale_price.append(room.list_price)
                    array_room_id.append(room.id)
        # Return False if there is no room type which belong to HLS category ###
        if not len(array_room_id):
            return False
        ########################################################################
        booking_item_xml = """
            <BookingItem>
                <RatePlanId></RatePlanId>
                <Adults></Adults>
                <Children></Children>
                <ExtraAdults></ExtraAdults>
                <ExtraChildren></ExtraChildren>
                <TaxFee></TaxFee>
                <TaxFeeArrival></TaxFeeArrival>
                <Discount></Discount>
                <Deposit></Deposit>
                <Amount></Amount>
            </BookingItem>
            """
        for booking in xmlstr.getiterator('Booking'):
            for tag in booking:
                if tag.tag == "Rooms":
                    for i in range(1, len(array_room_id)):
                        elementTree = ET.fromstring(booking_item_xml)
                        tag.append(elementTree)
                    break
        for booking in xmlstr.getiterator('Booking'):
            for tag in booking:
                if tag.tag == "CheckIn":
                    check_in = ""
                    for i in self.checkin:
                        if i == " ":
                            break
                        else:
                            check_in = check_in + i
                    tag.text = check_in
                elif tag.tag == "CheckOut":
                    check_out = ""
                    for i in self.checkout:
                        if i == " ":
                            break
                        else:
                            check_out = check_out + i
                    tag.text = check_out
                elif tag.tag == "GuestDetail":
                    for guest_info in tag:
                        if guest_info.tag == "FirstName":
                            guest_info.text = self.partner_id.name
                        elif guest_info.tag == "LastName":
                            guest_info.text = self.partner_id.last_name
                        elif guest_info.tag == "Email":
                            guest_info.text = self.partner_id.email
                        elif guest_info.tag == "Phone":
                            guest_info.text = self.partner_id.phone
                elif tag.tag == "Rooms":
                    i = 0
                    for booking_item in tag:
                        for room_info in booking_item:
                            RatePlanId = ""
                            if room_info.tag == "Amount":
                                amount_str = str(sale_price[i] * 1.02 * 1.1 * duration.days)
                                room_info.text = amount_str
                            elif room_info.tag == "RatePlanId":
                                category = hotel_room_obj.browse([array_room_id[i]]).categ_id
                                for rate_plan_line in category.rate_plan_line:
                                    RatePlanId = rate_plan_line.rate_plan_id
                                room_info.text = RatePlanId

                            elif room_info.tag == "TaxFee":
                                acco_tax = sale_price[i] * 0.02
                                vat_tax = (acco_tax + sale_price[i]) * 0.1
                                room_info.text = str((acco_tax + vat_tax) * duration.days)
                        i = i + 1
        body_req = ET.tostring(xmlstr, encoding='utf8', method='xml')
        return body_req

    @api.multi
    def define_inventory_form(self, room_types):
        hotel_room_type = self.env['hotel.room.type']
        hotel_room_obj = self.env['hotel.room']
        SaveInventory = """
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:soap="https://api.hotellinksolutions.com/services/inventory/soap" xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/">
            <soapenv:Header/>
            <soapenv:Body>
            <soap:SaveInventory>
            <Request>
            <Inventories>
            </Inventories>
            <Credential>
            <ChannelManagerUsername>tokyo</ChannelManagerUsername> 
            <ChannelManagerPassword>!?Hh7AC^v,*9uPd</ChannelManagerPassword> 
            <HotelId>93d2c493-35fa-1519615468-4b37-b5bb-181e59dbe9de</HotelId> 
            <HotelAuthenticationChannelKey>0f62852c65b34cbc19eb29d354936a0f</HotelAuthenticationChannelKey> 
            </Credential> 
            <Language>en</Language>
            </Request>
            </soap:SaveInventory>
            </soapenv:Body>
            </soapenv:Envelope>
            """
        element_saveInventory = ET.fromstring(SaveInventory)
        inventory = """
            <Inventory>
                <RoomId></RoomId>
                <Availabilities>
                </Availabilities>
            </Inventory>
            """
        room_qty = """
            <Availability>
                <DateRange>
                    <From></From>
                    <To></To>
                </DateRange>
                <Quantity></Quantity>
                <Action>Set</Action>
            </Availability>
            """
        availability = {}

        for type_id in room_types:
            check_in = parse(self.checkin)
            check_out = parse(self.checkout)
            date_qty = dict()
            while True:
                date_qty.update({check_in.isoformat(): 0})
                room_ids = hotel_room_obj.search([('categ_id', '=', type_id)])
                for r in room_ids:
                    available = 1
                    for line in r.room_reservation_line_ids:
                        line_check_in = parse(line.check_in)
                        line_check_out = parse(line.check_out)
                        if line.status != "cancel":
                            if line_check_in <= check_in <= line_check_out:
                                available = 0
                                break
                    for line in r.room_line_ids:
                        line_check_in = parse(line.check_in)
                        line_check_out = parse(line.check_out)
                        if line.status != "cancel":
                            if line_check_in <= check_in <= line_check_out:
                                available = 0
                                break
                    if available == 1:
                        date_qty[check_in.isoformat()] = date_qty[check_in.isoformat()] + 1

                check_in = check_in + datetime.timedelta(days=1)
                if check_in.date() == check_out.date():
                    break
            hls_room_id = hotel_room_type.browse([type_id]).room_type_id
            availability.update({hls_room_id: date_qty})

        for room_id in availability:
            inventory_element = ET.fromstring(inventory)
            for i in inventory_element.getiterator('RoomId'):
                i.text = room_id
            for i in inventory_element.getiterator('Availabilities'):
                for date in availability[room_id]:
                    element = ET.fromstring(room_qty)
                    for data in element.getiterator('From'):
                        data.text = date
                    for data in element.getiterator('To'):
                        data.text = date
                    for data in element.getiterator('Quantity'):
                        if availability[room_id][date] < 0:
                            data.text = str(0)
                        else:
                            data.text = str(availability[room_id][date])
                    i.append(element)

            for Inventories in element_saveInventory.getiterator('Inventories'):
                Inventories.append(inventory_element)
        Inventory_Body = ET.tostring(element_saveInventory, encoding='utf8', method='xml')
        return Inventory_Body

    ################################################
    # Inheritance functions ########################
    # @api.multi
    # def confirmed_reservation(self):
    #     res = super(save_booking, self).confirmed_reservation()
    #     headers = {"Content-Type": "application/xml"}
    #     body_req = self.define_notifybooking()
    #     print body_req
    #     if body_req:
    #         try:
    #             response = requests.post("https://api.hotellinksolutions.com/services/booking/soap",
    #                                      data=body_req, headers=headers)
    #             print "====response confirmed_reservation"
    #             print response.content
    #             str_xml = xmltodict.parse(response.content)
    #             str_json = json.dumps(str_xml)
    #             booking_hls = yaml.load(str_json)
    #             booking_resp = \
    #                 booking_hls['SOAP-ENV:Envelope']['SOAP-ENV:Body']['ns1:NotifyBookingsResponse'][
    #                     'NotifyBookingsResult'][
    #                     'Bookings']['ns1:BookingResponse']
    #             if booking_resp[0]['Success'] == "true":
    #                 room_types = self.define_room_types()
    #                 Inventory_Body = self.define_inventory_form(room_types)
    #                 # response = requests.post("https://api.hotellinksolutions.com/services/inventory/soap",
    #                 #                          data=Inventory_Body, headers=headers)
    #                 res = super(save_booking, self).write({'booking_id': booking_resp[0]['BookingId']})
    #             return res
    #         except requests.exceptions.ConnectionError:
    #             raise except_orm(_('Warning'), _('You tried to confirm reservation with no internet connection'))
    #     else:
    #         return res

    # @api.multi
    # def write(self, vals):
    #     headers = {"Content-Type": "application/xml"}
    #     write_con = ["BO", "AG", "MO", "OT", "BW"]
    #     booking_id_checking = "BookingFromOTA"

    #     # used for cases confirm or cancel booking from OTA ###########
    #     if "BookingFromOTA" in vals:
    #         del vals["BookingFromOTA"]
    #         res = super(save_booking, self).write(vals)
    #         return res
    #     ##############################################################

    #     # raise exception or not #####################################################
    #     if self.booking_id:
    #         booking_id_checking = self.booking_id[0] + self.booking_id[1]
    #         if self.state == "draft":
    #             booking_id_checking = "BookingFromOTA"
    #     if (self.state == 'cancel') or (self.state == 'done') or (booking_id_checking in write_con):
    #         raise except_orm(_('Warning'), _("You cant update this reservation!!!"))
    #     ##############################################################################
    #     res = super(save_booking, self).write(vals)
    #     if self.booking_id:
    #         if vals.get('reservation_line'):
    #             if self.state in ['confirm']:
    #                 body_req = self.define_notifybooking()
    #                 if body_req:
    #                     # NotifyBooing ##############################################################################
    #                     body_req_element = ET.fromstring(body_req)
    #                     for BookingId in body_req_element.getiterator('BookingId'):
    #                         BookingId.text = self.booking_id
    #                     for NotificationType in body_req_element.getiterator('NotificationType'):
    #                         NotificationType.text = "Update"
    #                     write_data = ET.tostring(body_req_element, encoding='utf8', method='xml')
    #                     try:
    #                         response = requests.post("https://api.hotellinksolutions.com/services/booking/soap",
    #                                                  data=write_data, headers=headers)
    #                     except requests.exceptions.ConnectionError:
    #                         raise except_orm(_('No Internet Connection'), _('Please Try again later'))
    #                     # SaveInventory ##############################################################################
    #                     room_types = self.define_room_types()
    #                     Inventory_Body = self.define_inventory_form(room_types)
    #                     try:
    #                         # response = requests.post("https://api.hotellinksolutions.com/services/inventory/soap",
    #                         #                          data=Inventory_Body, headers=headers)
    #                         return res
    #                     except requests.exceptions.ConnectionError:
    #                         raise except_orm(_('No Internet Connection'), _('Please Try again later'))
    #                     ##############################################################################################
    #                 else:
    #                     return res
    #             else:
    #                 return res
    #     else:
    #         return res

    # @api.multi
    # def cancel_reservation(self):
    #     cancel_con = ["BO", "AG", "MO", "OT", "BW"]
    #     headers = {"Content-Type": "application/xml"}
    #     if self.booking_id:
    #         if (self.booking_id[0] + self.booking_id[1]) in cancel_con:
    #             raise except_orm(_('Warning'), _('You can not cancel Reservations which from OTA'))
    #         res = super(save_booking, self).cancel_reservation()
    #         cancel_booking_str = """
    #             <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:soap="https://api.hotellinksolutions.com/services/booking/soap" xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/">
    #                 <soapenv:Header/>
    #                 <soapenv:Body>
    #                 <soap:NotifyBookings>
    #                 <Request>
    #                 <Bookings>
    #                     <Booking>
    #                     <NotificationType>Cancel</NotificationType>
    #                     <BookingId></BookingId>
    #                     </Booking>
    #                 </Bookings>
    #                 <Credential>
    #                 <ChannelManagerUsername>tokyo</ChannelManagerUsername>
    #                 <ChannelManagerPassword>!?Hh7AC^v,*9uPd</ChannelManagerPassword>
    #                 <HotelId>93d2c493-35fa-1519615468-4b37-b5bb-181e59dbe9de</HotelId>
    #                 <HotelAuthenticationChannelKey>0f62852c65b34cbc19eb29d354936a0f</HotelAuthenticationChannelKey>
    #                 </Credential>
    #                 <Language>en</Language>
    #                 <Language>en</Language>
    #                 </Request>
    #                 </soap:NotifyBookings>
    #                 </soapenv:Body>
    #             </soapenv:Envelope>
    #         """
    #         cancel_element = ET.fromstring(cancel_booking_str)
    #         for Id in cancel_element.getiterator('BookingId'):
    #             Id.text = self.booking_id
    #         body_req = ET.tostring(cancel_element, encoding='utf8', method='xml')
    #         try:
    #             response = requests.post("https://api.hotellinksolutions.com/services/booking/soap",
    #                                      data=body_req, headers=headers)
    #             room_types = self.define_room_types()
    #             Inventory_Body = self.define_inventory_form(room_types)
    #             # response = requests.post("https://api.hotellinksolutions.com/services/inventory/soap",
    #             #                          data=Inventory_Body, headers=headers)
    #         except requests.exceptions.ConnectionError:
    #             raise except_orm(_('Warning'), _('You tried to cancel reservation with No internet connection'))
    #         return res
    #     else:
    #         res = super(save_booking, self).cancel_reservation()
    #         return res
            
    ###############################################


class HotelRoomType(models.Model):
    _inherit = 'hotel.room.type'
    rate_plan_line = fields.One2many('roomtype.rate_plan', 'hotel_room_type_id', 'Lines')
    room_type_id = fields.Char('Room TypeID')


class RatePlant(models.Model):
    _name = 'roomtype.rate_plan'
    name = fields.Char('Name', select=True, required=True)
    rate_plan_id = fields.Char('Id', required=True)
    hotel_room_type_id = fields.Many2one('hotel.room.type')


class HotelRoom(models.Model):
    _inherit = 'hotel.room'
    room_type_id = fields.Char('Type ID', related='categ_id.room_type_id')


# class HotelFolioLine(models.Model):
#     _inherit = 'hotel.folio.line'

#     @api.multi
#     def unlink(self):
#         headers = {"Content-Type": "application/xml"}
#         if self.room_no.categ_id.categ_id.name == "HLS":
#             room_type = [self.room_no.categ_id.id]
#             reservation_obj = self.folio_id.reservation_id
#             res = super(HotelFolioLine, self).unlink()
#             Inventory_Body = reservation_obj.define_inventory_form(room_type)
#             # response = requests.post("https://api.hotellinksolutions.com/services/inventory/soap",
#             #                          data=Inventory_Body, headers=headers)
#             return res
#         else:
#             res = super(HotelFolioLine, self).unlink()
#             return res
