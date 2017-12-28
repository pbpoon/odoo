# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class Invite(models.TransientModel):
    """ Wizard to invite new user """
    _name = 'mail.invite.user'
    _description = 'Invite User wizard'

    email = fields.Text(string='Invite User')

    @api.multi
    def invite_new_user(self):
        """Process new email addresses : create new users """
        invite_emails = [email for email in self.email.split('\n')]
        return self.env['res.users'].web_dashboard_create_users(invite_emails)
