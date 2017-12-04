# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.multi
    def post(self):
        '''Sales orders are sent automatically upon the transaction is posted.
        if the option 'automatic_invoice' is enabled, an invoice is created for each sales orders and they are linked
        to the account.payment using the inherits.
        If not, the sales orders are posted without any further invoices.
        '''
        automatic_invoice = self.env['ir.config_parameter'].sudo().get_param('website_sale.automatic_invoice')
        for trans in self.filtered(lambda t: t.sale_order_ids):
            for so in trans.sale_order_ids.filtered(lambda so: so.state in ('draft', 'sent')):
                old_state = so.state
                so.action_confirm()
                so._log_transaction_so_message(old_state, trans)

            trans.sale_order_ids._force_lines_to_invoice_policy_order()

            if not automatic_invoice:
                continue

            invoice_ids = trans.sale_order_ids.action_invoice_create()
            if invoice_ids:
                for inv in self.env['account.invoice'].browse(invoice_ids):
                    inv._log_transaction_invoice_creation_message(trans)
            trans.invoice_ids = [(6, 0, invoice_ids)]
        return super(PaymentTransaction, self.filtered(lambda t: not t.authorized)).post()

    @api.multi
    def mark_to_capture(self):
        # The sale orders are confirmed if the transaction are set to 'authorized' directly.
        for trans in self.filtered(lambda t: not t.authorized and t.acquirer_id.capture_manually):
            for so in trans.sale_order_ids.filtered(lambda so: so.state in ('draft', 'sent')):
                old_state = so.state
                so.action_confirm()
                so._log_transaction_so_message(old_state, trans)
        super(PaymentTransaction, self).mark_to_capture()

    @api.multi
    def mark_as_pending(self):
        # The quotations are sent for each remaining sale orders in state 'draft'.
        super(PaymentTransaction, self).mark_as_pending()
        for trans in self.filtered(lambda t: t.pending):
            for so in trans.sale_order_ids.filtered(lambda so: so.state == 'draft'):
                old_state = so.state
                so.force_quotation_send()
                so._log_transaction_so_message(old_state, trans)

    # --------------------------------------------------
    # Tools for payment
    # --------------------------------------------------

    def confirm_sale_token(self):
        """ Confirm a transaction token and call SO confirmation if it is a success.
        :return: True if success; error string otherwise """
        self.ensure_one()
        if self.payment_token_id:
            try:
                s2s_result = self.s2s_do_transaction()
            except Exception as e:
                _logger.warning(
                    _("<%s> transaction (%s) failed: <%s>") %
                    (self.acquirer_id.provider, self.id, str(e)))
                return 'pay_sale_tx_fail'

            if not s2s_result or not self.pending or\
                (self.acquirer_id.capture_manually and not self.authorized or self.state == 'draft'):
                _logger.warning(
                    _("<%s> transaction (%s) invalid state: %s") %
                    (self.acquirer_id.provider, self.id, self.state_message))
                return 'pay_sale_tx_state'
        return 'pay_sale_tx_token'

    def _check_or_create_sale_tx(self, order, acquirer, payment_token=None, tx_type='form', add_tx_values=None, reset_draft=True):
        tx = self
        if not tx:
            tx = self.search([('reference', '=', order.name)], limit=1)

        if tx.state == 'cancelled':  # filter incorrect states
            tx = False
        if (tx and tx.acquirer_id != acquirer) or (tx and order not in tx.sale_order_ids):  # filter unmatching
            tx = False
        if tx and payment_token and tx.payment_token_id and payment_token != tx.payment_token_id:  # new or distinct token
            tx = False

        # still draft tx, no more info -> rewrite on tx or create a new one depending on parameter
        if tx and tx.state == 'draft':
            tx = False

        if not tx:
            if not add_tx_values:
                add_tx_values = {}
            add_tx_values['type'] = tx_type
            tx = order.create_payment_transaction(acquirer, payment_token=payment_token)
            if add_tx_values:
                tx.write(add_tx_values)

        return tx

    def render_sale_button(self, order, return_url, submit_txt=None, render_values=None):
        values = {
            'return_url': return_url,
            'partner_id': order.partner_shipping_id.id or order.partner_invoice_id.id,
            'billing_partner_id': order.partner_invoice_id.id,
        }
        if render_values:
            values.update(render_values)
        return self.acquirer_id.with_context(submit_class='btn btn-primary', submit_txt=submit_txt or _('Pay Now')).sudo().render(
            self.reference,
            order.amount_total,
            order.pricelist_id.currency_id.id,
            values=values,
        )
