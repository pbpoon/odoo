# coding: utf-8

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_transaction_ids = fields.One2many('payment.transaction', 'payment_id', string='Transactions')
    payment_transaction_id = fields.Many2one('payment.transaction', string='Transaction',
                                             compute='_compute_payment_transaction_id')
    payment_transaction_authorized = fields.Boolean(related='payment_transaction_id.authorized')
    refund_payment_id = fields.Many2one('account.payment', string='Payment to Refund')

    @api.depends('payment_transaction_ids')
    def _compute_payment_transaction_id(self):
        '''Compute the payment_transaction_id field as the other side of a one2one relation
        between account.payment / payment.transaction.
        '''
        for pay in self:
            pay.payment_transaction_id = pay.payment_transaction_ids and pay.payment_transaction_ids[0] or False

    @api.multi
    def _prepare_account_payment_refund_vals(self):
        '''Create dictionary values to create an account.payment record representing
        a refund of this payment.
        :return: a dictionary.
        '''
        self.ensure_one()
        payment_type_map = {'outbound': 'inbound', 'inbound': 'outbound'}
        return {
            'name': _('Refund: %s') % self.name,
            'amount': -self.amount,
            'partner_id': self.partner_id.id,
            'partner_type': self.partner_type,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_type': payment_type_map.get(self.payment_type, self.payment_type),
            'refund_payment_id': self.id,
            'state': 'draft',
        }

    @api.multi
    def post(self):
        # If some payments are refunds of others ones, unreconcile them first and then,
        # reconcile payments together.
        super(AccountPayment, self).post()
        for pay in self.filtered(lambda p: p.refund_payment_id):
            pay.move_line_ids.mapped('move_id.line_ids').remove_move_reconcile()
            (pay.move_line_ids + pay.refund_payment_id.move_line_ids).reconcile()

    @api.multi
    def create_refund(self):
        '''Refund the selected posted payments.
        :return: A list of draft payments to refund them.
        '''
        if any(p.state in ['draft', 'cancelled'] for p in self):
            raise UserError(_('Only a posted payment can be refunded.'))
        if any(p.refund_payment_id for p in self):
            raise UserError(_('Only not refund payment can be refunded.'))

        refund_payments = self.env['account.payment']
        for pay in self:
            refund_payments += self.create(pay._prepare_account_payment_refund_vals())

        return refund_payments

    @api.multi
    def _check_payment_transaction_id(self):
        if any(not p.payment_transaction_ids for p in self):
            raise ValidationError(_('Only payments linked to some transactions can be proceeded.'))

    @api.multi
    def action_capture(self):
        self._check_payment_transaction_id()
        payment_transaction_ids = self.mapped('payment_transaction_ids')
        if any(not t.authorized for t in payment_transaction_ids):
            raise ValidationError(_('Only transactions having the Authorized status can be captured.'))
        payment_transaction_ids.s2s_capture_transaction()

    @api.multi
    def action_void(self):
        self._check_payment_transaction_id()
        payment_transaction_ids = self.mapped('payment_transaction_ids')
        if any(not t.authorized for t in payment_transaction_ids):
            raise ValidationError(_('Only transactions having the Authorized status can be voided.'))
        payment_transaction_ids.s2s_void_transaction()

    @api.constrains('payment_transaction_ids')
    def _check_only_one_transaction(self):
        '''Because we are simulating an one2one relation between account.payment/payment.transaction,
        We need to ensure the payment_transaction_ids has an arity of [0..1].
        '''
        for pay in self:
            if len(pay.payment_transaction_ids) > 1:
                raise UserError(_('Only one transaction per payment is allowed!'))
