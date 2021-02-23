from openerp.osv import osv, fields
from openerp import api, models
from openerp.http import request
import time
from datetime import datetime, timedelta

class ResPartner(osv.Model):
    _inherit ='res.partner'

    _columns = {
        'last_name': fields.char("Last Name")
    }

class ResUsers(models.Model):
    _inherit = 'res.users'

    def _check_session_validity(self, db, uid, passwd):
        if not request:
            return
        session = request.session
        current_time = '{:%H%M}'.format(datetime.now()+ timedelta(hours=7))
        try:
            if current_time in ['0745','1800'] and session.uid!=1:
                if session.db and session.uid:
                    time.sleep(60)
                    session.logout(keep_db=True)
        except OSError:
            pass
        return

    def check(self, db, uid, passwd):
        res = super(ResUsers, self).check(db, uid, passwd)
        self._check_session_validity(db, uid, passwd)
        return res