import datetime
from openerp import models, fields, api


class HotelReportWizard(models.TransientModel):
    _name = 'hotel.report.wizard'
    _rec_name = 'report_date'

    @api.multi
    def _defaults_date_start(self):
        date_start = datetime.datetime.now().strftime("%Y-%m-%d 07:00:00")
        return date_start

    report_date = fields.Datetime('Report Date', default = _defaults_date_start)

    @api.multi
    def print_apartment_report(self):
        data = {
            'ids': self.ids,
            'model': 'hotel.folio',
            'form': self.read(['report_date'])[0]
        }
        return self.env['report'].get_action(self, 'hotel.report_hotel_folio_apartment',
                                             data=data)

    @api.multi
    def print_daily_report(self):
        data = {
            'ids': self.ids,
            'model': 'hotel.folio',
            'form': self.read(['report_date'])[0]
        }
        return self.env['report'].get_action(self, 'hotel.report_hotel_folio_daily',
                                             data=data)