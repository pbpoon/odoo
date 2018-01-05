# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_ids = fields.Many2many('account.payment', 'account_payment_sale_order_rel', 'sale_order_id', 'account_payment_id',
                                   string='Payments', readonly=True)
    payment_ids_nbr = fields.Integer(string='# of Payments', compute='_compute_payment_ids')
    payment_tx_id = fields.Many2one('payment.transaction', string='Last Transaction', compute='_compute_payment_ids')

    @api.depends('payment_ids')
    def _compute_payment_ids(self):
        for so in self:
            so.payment_ids_nbr = len(so.payment_ids)
            if not so.payment_ids:
                continue
            transactions = [pay.payment_transaction_id for pay in so.payment_ids if pay.payment_transaction_id]
            so.payment_tx_id = transactions and transactions[0] or None

    @api.multi
    def get_portal_transactions(self):
        return self.mapped('payment_ids.payment_transaction_ids')\
            .filtered(lambda trans: trans.state == 'posted' or (trans.state == 'draft' and trans.pending))

    @api.multi
    def get_portal_last_transaction(self):
        return self.sudo().payment_tx_id

    @api.multi
    def _log_transaction_so_message(self, old_state, transaction):
        self.ensure_one()
        message = _('This sale order has been updated automatically by the transaction %s:') % transaction._get_oe_log_html()
        values = ['%s: %s -> %s' % (_('Status'), old_state, self.state), '%s: %s' % (_('Date'), fields.datetime.now())]
        message += '<ul><li>' + '</li><li>'.join(values) + '</li></ul>'
        self.message_post(body=message)

    @api.multi
    def create_payment_transaction(self, acquirer, payment_token=None, save_token=None):
        currency = self[0].pricelist_id.currency_id
        if any([so.pricelist_id.currency_id != currency for so in self]):
            raise UserError(_('A transaction can\'t be linked to sales orders having different currencies.'))
        partner = self[0].partner_id
        if any([so.partner_id != partner for so in self]):
            raise UserError(_('A transaction can\'t be linked to sales orders having different partners.'))
        if payment_token and payment_token.acquirer_id != acquirer:
            raise UserError(_('Invalid token found: token acquirer %s != %s') % (payment_token.acquirer_id.name, acquirer.name))
        if payment_token and payment_token.partner_id != partner:
            raise UserError(_('Invalid token found: token partner %s != %s') % (payment_token.partner.name, partner.name))

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
            'sale_order_ids': [(6, 0, self.ids)],
            'payment_token_id': payment_token_id,
        }

        return self.env['payment.transaction'].create(transaction_vals)

    @api.multi
    def action_view_payments(self):
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Payment(s)'),
            'res_model': 'account.payment',
        }
        payment_ids = self.payment_ids
        if len(payment_ids) == 1:
            action.update({
                'res_id': payment_ids[0].id,
                'view_mode': 'form',
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', payment_ids.ids)],
            })
        return action

    @api.multi
    def _force_lines_to_invoice_policy_order(self):
        for line in self.order_line:
            if self.state in ['sale', 'done']:
                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
            else:
                line.qty_to_invoice = 0
