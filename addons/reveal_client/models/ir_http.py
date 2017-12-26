import odoo
from odoo import models, api
from threading import Thread
from odoo.http import request
from odoo.modules.registry import Registry

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls):
        res = super(IrHttp, cls)._dispatch()

        if request.is_frontend and not request.session.uid:
            path = request.httprequest.path
            ip = request.httprequest.remote_addr
            if path != "/website/translations":
                thread = Thread(target=cls.threaded_function, args=(
                    request.env.cr.dbname,
                    request.env.uid,
                    path,
                    ip
                ))
                thread.start()
        return res

    def threaded_function(dbname, uid, path, ip):
        with api.Environment.manage():
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, uid, {})
                env['crm.lead.rule'].sudo().test_rule(path, ip)
