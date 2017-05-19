# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug import url_encode
from odoo import api, fields, models, _


class AccountRegisterPayments(models.TransientModel):
    _inherit = "account.register.payments"

    expense_sheet_id = fields.Many2one('hr.expense.sheet')

    @api.model
    def default_get(self, fields):
        vals = super(AccountRegisterPayments, self).default_get(fields)
        if not vals.get('expense_sheet_id'):
            return vals
        expense_sheet = self.env['hr.expense.sheet'].browse(vals.get('expense_sheet_id'))
        partner = expense_sheet.address_id or expense_sheet.employee_id.address_home_id
        vals.update(
            partner_type='supplier',
            payment_type='outbound',
            amount=abs(expense_sheet.total_amount),
            currency_id=expense_sheet.currency_id.id,
            partner_id=partner.id
        )
        return vals

    def _prepare_expense_payment_vals(self):
        partner = self.expense_sheet_id.address_id or self.expense_sheet_id.employee_id.address_home_id
        return {
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_date': self.payment_date,
            'communication': self.communication,
            'partner_type': 'supplier',
            'payment_type': 'outbound',
            'amount': abs(self.expense_sheet_id.total_amount),
            'currency_id': self.expense_sheet_id.currency_id.id,
            'partner_id': partner.id
        }

    @api.multi
    def get_payments_vals(self):
        self.ensure_one()
        res = super(AccountRegisterPayments, self).get_payments_vals()
        if not self.expense_sheet_id:
            return res
        return [self._prepare_expense_payment_vals()]

    def _create_payments(self):
        payment = super(AccountRegisterPayments, self)._create_payments()
        if not self.expense_sheet_id:
            return payment

        # Log the payment in the chatter
        msg = _("A payment of %s %s with the reference <a href='/mail/view?%s'>%s</a> related to your expense <i>%s</i> has been made.")
        body = (msg % (payment.amount, payment.currency_id.symbol, url_encode({'model': 'account.payment', 'res_id': payment.id}), payment.name, self.expense_sheet_id.name))
        self.expense_sheet_id.message_post(body=body)

        # Reconcile the payment and the expense, i.e. lookup on the payable account move lines
        account_move_lines_to_reconcile = self.env['account.move.line']
        for line in payment.move_line_ids + self.expense_sheet_id.account_move_id.line_ids:
            if line.account_id.internal_type == 'payable':
                account_move_lines_to_reconcile |= line
        account_move_lines_to_reconcile.reconcile()
        return payment

    @api.multi
    def create_payments(self):
        self.ensure_one()
        res = super(AccountRegisterPayments, self).create_payments()
        if not self.expense_sheet_id:
            return res
        return {'type': 'ir.actions.act_window_close'}
