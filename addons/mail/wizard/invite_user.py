# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class Invite(models.TransientModel):
    """ Wizard to invite new user """
    _name = 'mail.invite.user'
    _description = 'Invite User wizard'

    email = fields.Text(string='Invite User')

    @api.multi
    def invite_new_user(self):
        """Process new email addresses : create new users """
        invite_emails = [email for email in self.email.split('\n')]
        is_valid_emails = all([tools.email_re.findall(email) for email in invite_emails])
        if is_valid_emails:
            return self.env['res.users'].web_dashboard_create_users(invite_emails)
        raise ValidationError(_('Invalid Email! Please enter a valid email address.'))
