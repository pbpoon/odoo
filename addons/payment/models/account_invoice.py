# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def _log_transaction_invoice_update_message(self, transaction):
        self.ensure_one()
        message = _('This invoice has been updated automatically by the transaction %s:') % transaction._get_oe_log_html()
        values = ['%s: %s -> %s' % (_('Status'), 'draft', self.state), '%s: %s' % (_('Date'), fields.datetime.now())]
        message += '<ul><li>' + '</li><li>'.join(values) + '</li></ul>'
        self.message_post(body=message)

    @api.multi
    def create_payment_transaction(self, acquirer, payment_token=None, save_token=None):
        currency = self[0].currency_id
        if any([inv.currency_id != currency for inv in self]):
            raise UserError(_('A transaction can\'t be linked to invoices having different currencies.'))
        partner = self[0].partner_id
        if any([inv.partner_id != partner for inv in self]):
            raise UserError(_('A transaction can\'t be linked to invoices having different partners.'))
        if payment_token and payment_token.acquirer_id != acquirer:
            raise UserError(
                _('Invalid token found: token acquirer %s != %s') % (payment_token.acquirer_id.name, acquirer.name))
        if payment_token and payment_token.partner_id != partner:
            raise UserError(
                _('Invalid token found: token partner %s != %s') % (payment_token.partner.name, partner.name))

        amount = sum(self.mapped('amount_total'))
        payment_token_id = payment_token and payment_token.id or None
        transaction_type = 'form_save' if save_token else 'form'

        transaction_vals = {
            'acquirer_id': acquirer.id,
            'type': transaction_type,
            'amount': amount,
            'currency_id': currency.id,
            'partner_id': partner.id,
            'partner_country_id': partner.country_id.id,
            'invoice_ids': [(6, 0, self.ids)],
            'payment_token_id': payment_token_id,
        }

        return self.env['payment.transaction'].create(transaction_vals)
