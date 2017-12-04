# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def _log_transaction_invoice_creation_message(self, transaction):
        self.ensure_one()
        message = _('This invoice has been created automatically by the transaction %s:') % transaction.reference
        values = ['%s: %s' % (_('Date'), fields.datetime.now())]
        message += '<ul><li>' + '</li><li>'.join(values) + '</li></ul>'
        self.message_post(body=message)
