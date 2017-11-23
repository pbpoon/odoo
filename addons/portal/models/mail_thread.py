# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    _mail_post_token_field = 'access_token' # token field for external posts, to be overridden

    website_message_ids = fields.One2many('mail.message', 'res_id', string='Website Messages',
        domain=lambda self: [('model', '=', self._name), ('message_type', '=', 'comment')], auto_join=True,
        help="Website communication history")

    shared = fields.Boolean('Check shared Document', compute="_compute_share")

    def _compute_share(self):
        # when Access through sudo in portal env.user will be super user
        user_id = self.env.context.get('uid')
        partner = self.env['res.users'].browse(user_id).partner_id
        for record in self.filtered(lambda x: partner in x.message_follower_ids.mapped('partner_id') and (partner != x.partner_id) and (x.create_uid.id != user_id)):
            record.shared = True
