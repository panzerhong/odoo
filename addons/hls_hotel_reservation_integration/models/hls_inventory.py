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


class HlsInventory(models.TransientModel):
    _name = 'hls.inventory'
    _description = 'hls inventory'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)

    @api.multi
    def update_inventory(self):
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
        start_date = parse(self.start_date).date()
        end_date = parse(self.end_date).date() + datetime.timedelta(days=1)
        date_qty = dict()
        type_ids = []
        for room_type in hotel_room_type.search([]):
            if room_type.categ_id.name == "HLS":
                type_ids.append(room_type.id)
        room_ids = hotel_room_obj.search([('categ_id_2.name', '=', 'Standard'),('categ_id.name','!=','Close')])
        while True:
            date_qty.update({start_date.isoformat(): 0})
            for r in room_ids:
                available = 1
                for line in r.room_reservation_line_ids:
                    line_check_in = parse(line.check_in).date()
                    line_check_out = parse(line.check_out).date()
                    if line.status != "cancel":
                        if line_check_in <= start_date < line_check_out:
                            available = 0
                            break
                for line in r.room_line_ids:
                    line_check_in = parse(line.check_in)
                    line_check_out = parse(line.check_out)
                    if line.status != "cancel":
                        if line_check_in <= start_date < line_check_out:
                            available = 0
                            break
                if available == 1:
                    date_qty[start_date.isoformat()] = date_qty[start_date.isoformat()] + 1
            start_date = start_date + datetime.timedelta(days=1)
            if start_date == end_date:
                break
        availability.update({room_ids[0].room_type_id: date_qty})

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
        try:
            headers = {"Content-Type": "application/xml"}
            response = requests.post("https://api.hotellinksolutions.com/services/inventory/soap",
                                     data=Inventory_Body, headers=headers)
            _logger.info(response.content)

        except requests.exceptions.ConnectionError:
            raise except_orm(_('Warning'), _('You tried to Update with No internet connection'))
