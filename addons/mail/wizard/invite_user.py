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
        user = self.env['res.users']
        invite_emails = [email for email in self.email.split('\n')]
        emails = set(invite_emails) - set(user.search([]).mapped('login'))
        for email in emails:
            default_values = {'login': email, 'name': email.split('@')[0], 'email': email, 'active': True}
            user.with_context(signup_valid=True).create(default_values)
        return True
