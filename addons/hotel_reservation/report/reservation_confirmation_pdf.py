from openerp import models
import time
import datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.report import report_sxw


class ConfirmationDetails(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(ConfirmationDetails, self).__init__(cr, uid, name,
                                                      context)
        self.localcontext.update({"get_duration": self.get_duration,
                                  "get_rooms": self.get_rooms,
                                 # "get_type": self.get_type,
                                  "get_rate_data": self.get_rate_data,
                                  #"get_tot_hotel": self.get_tot_hotel,
                                  "add_time": self.add_time})

    def get_duration(self, checkin, checkout):
        server_dt = DEFAULT_SERVER_DATETIME_FORMAT
        chkin_dt = datetime.datetime.strptime(checkin, server_dt)
        chkout_dt = datetime.datetime.strptime(checkout, server_dt)
        dur = chkout_dt - chkin_dt
        dur =  dur + datetime.timedelta(days=1)
        return int(dur.days)

    def get_rooms(self, reservation_line):
        rooms = 0
        for res in reservation_line:
            rooms = rooms + len(res.reserve)
        return int(rooms)

    def get_rate_data(self, reservation_line, pricelist):
        rate = {}
        for res in reservation_line:
            for room in res.reserve:
                category_name = room.categ_id.name
                for version in pricelist.version_id:
                    in_pricelist = False
                    for item in version.items_id:
                        if item.categ_id.name == category_name:
                            price = (room.list_price * (1 + item.price_discount) + item.price_surcharge)
                            if category_name not in rate:
                                rate.update({category_name: [price,1]})
                                in_pricelist = True
                                break
                            else:
                                rate[category_name][0] = rate[category_name][0]+price
                                rate[category_name][1] = rate[category_name][1]+1
                                in_pricelist = True
                                break
                    if not in_pricelist:
                        if category_name not in rate:
                            rate.update({category_name: [room.list_price,1]})
                        else:
                            rate[category_name][0] = rate[category_name][0]+room.list_price
                            rate[category_name][1] = rate[category_name][1] +1
        return rate

    def add_time(self, date):
        server_dt = DEFAULT_SERVER_DATETIME_FORMAT
        date = datetime.datetime.strptime(date, server_dt)
        h = datetime.timedelta(hours=7)
        return date + h


class ReportConfirmReservation(models.AbstractModel):
    _name = "report.hotel_reservation.reservation_confirmation_report"
    _inherit = "report.abstract_report"
    _template = "hotel_reservation.reservation_confirmation_report"
    _wrapped_report_class = ConfirmationDetails