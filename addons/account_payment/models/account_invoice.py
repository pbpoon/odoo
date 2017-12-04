# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    payment_ids_nbr = fields.Integer(string='# of Payments', compute='_compute_payment_ids')
    payment_tx_id = fields.Many2one('payment.transaction', string='Last Transaction', compute='_compute_payment_ids')

    @api.depends('payment_ids')
    def _compute_payment_ids(self):
        for inv in self:
            inv.payment_ids_nbr = len(inv.payment_ids)
            if not inv.payment_ids:
                continue
            inv.payment_tx_id = next(pay.payment_transaction_id for pay in inv.payment_ids if pay.payment_transaction_id)

    @api.multi
    def get_portal_transactions(self):
        return self.mapped('payment_ids.payment_transaction_ids')\
            .filtered(lambda trans: trans.state == 'posted' or (trans.state == 'draft' and trans.pending))

    def action_view_payments(self):
        action = {
            'name': _('Payment(s)'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'target': 'current',
        }
        payment_ids = self.mapped('payment_ids')
        if len(payment_ids) == 1:
            action['res_id'] = payment_ids.ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', payment_ids.ids)]
        return action
