# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def default_share_link(self):
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        res = False
        if active_model:
            model = self.env[active_model]
            if isinstance(model, self.pool['portal.mixin']):
                doc_url = model.browse(active_id).portal_url
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                res = base_url + doc_url
        return res

    share_link = fields.Char(string="Document link", default=default_share_link)
