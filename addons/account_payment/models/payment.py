# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    account_invoice_id = fields.Many2one('account.invoice', string='Invoice')

    def form_feedback(self, data, acquirer_name):
        """ Override to confirm the invoice, if defined, and if the transaction is done. """
        tx = None
        res = super(PaymentTransaction, self).form_feedback(data, acquirer_name)

        # fetch the tx
        tx_find_method_name = '_%s_form_get_tx_from_data' % acquirer_name
        if hasattr(self, tx_find_method_name):
            tx = getattr(self, tx_find_method_name)(data)

        if tx and tx.account_invoice_id:
            _logger.info(
                '<%s> transaction <%s> processing form feedback for invoice <%s>: tx ref:%s, tx amount: %s',
                acquirer_name, tx.id, tx.account_invoice_id.id, tx.reference, tx.amount)
            tx._confirm_invoice()

        return res

    def confirm_invoice_token(self):
        """ Confirm a transaction token and call SO confirmation if it is a success.

        :return: True if success; error string otherwise """
        self.ensure_one()
        if self.payment_token_id and self.partner_id == self.account_invoice_id.partner_id:
            try:
                s2s_result = self.s2s_do_transaction()
                return True
            except Exception as e:
                _logger.warning(
                    _("<%s> transaction (%s) failed : <%s>") %
                    (self.acquirer_id.provider, self.id, str(e)))
                return 'pay_invoice_tx_fail'
        return 'pay_invoice_tx_token'

    def render_invoice_button(self, invoice, return_url, submit_txt=None, render_values=None):
        values = {
            'return_url': return_url,
            'partner_id': invoice.partner_id.id,
        }
        if render_values:
            values.update(render_values)
        return self.acquirer_id.with_context(submit_class='btn btn-primary', submit_txt=submit_txt or _('Pay Now')).sudo().render(
            self.reference,
            invoice.amount_total,
            invoice.currency_id.id,
            values=values,
        )

    def _check_or_create_invoice_tx(self, invoice, acquirer, payment_token=None, tx_type='form', add_tx_values=None):
        tx = self
        if not tx:
            tx = self.search([('reference', '=', invoice.number)], limit=1)

        if tx and tx.state in ['error', 'cancel']:  # filter incorrect states
            tx = False
        if (tx and acquirer and tx.acquirer_id != acquirer) or (tx and tx.account_invoice_id != invoice):  # filter unmatching
            tx = False
        if tx and tx.payment_token_id and payment_token and payment_token != tx.payment_token_id:  # new or distinct token
            tx = False

        # still draft tx, no more info -> create a new one
        if tx and tx.state == 'draft':
            tx = False

        if not tx:
            if not add_tx_values:
                add_tx_values = {}
            add_tx_values['type'] = tx_type
            tx = invoice.create_payment_transaction(acquirer, payment_token=payment_token)
            if add_tx_values:
                tx.write(add_tx_values)

        return tx
