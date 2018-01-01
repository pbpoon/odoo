from odoo import models, api
from threading import Thread
from odoo.http import request
from odoo.modules.registry import Registry


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls):
        res = super(IrHttp, cls)._dispatch()

        if 'reveal' not in request.session and request.is_frontend and request.httprequest.method == 'GET' and request._request_type == 'http' and not request.session.uid:
            args = (request.env.cr.dbname, request.env.uid, request.httprequest.path, request.httprequest.remote_addr)
            Thread(target=cls.process_reveal_request, args=args).start()
            request.session['reveal'] = True
        return res

    def process_reveal_request(dbname, uid, path, ip):
        with api.Environment.manage():
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, uid, {})
                env['crm.lead.rule'].sudo().test_rule(path, ip)
