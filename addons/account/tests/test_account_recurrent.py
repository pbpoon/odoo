# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.addons.account.tests.account_test_classes import AccountingTestCase


class TestAccountRecurrent(AccountingTestCase):

    def apply_vendor_cron(self):
        self.env.ref('account.recurrent_vendor_bills_cron').method_direct_trigger()

    def apply_journal_entries_cron(self):
        self.env.ref('account.recurrent_journal_entries_cron').method_direct_trigger()

    def test_create_recurring_vendor_bills(self):
        AccountInvoice = self.env['account.invoice']
        invoice_account_id = self.env['account.account'].search([('user_type_id', '=', self.ref('account.data_account_type_receivable'))], limit=1).id
        invoice_line_account_id = self.env['account.account'].search([('user_type_id', '=', self.ref('account.data_account_type_expenses'))], limit=1).id
        purchase_journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)

        invoice_line_data = [
            (0, 0,
                {
                    'product_id': self.ref('product.product_product_4'),
                    'name': 'product 4 that cost 100',
                    'quantity': 1.0,
                    'price_unit': 100.0,
                    'account_id': invoice_line_account_id,
                    'name': 'product test 4',
                }
             ),
            (0, 0,
                {
                    'product_id': self.ref('product.product_product_5'),
                    'name': 'product 5 that cost 200',
                    'quantity': 2.0,
                    'price_unit': 200.0,
                    'account_id': invoice_line_account_id,
                    'name': 'product test 5',
                }
             )
        ]

        # Create an invoice dated 2 months before today
        invoice = AccountInvoice.create({
            'partner_id': self.ref('base.res_partner_2'),
            'account_id': invoice_account_id,
            'name': 'invoice test recurrent',
            'type': 'in_invoice',
            'reference_type': 'none',
            'date_invoice': datetime.today() + relativedelta(months=-2),
            'journal_id': purchase_journal.id,
            'is_recurrency_enabled': True,
            'recurrency_interval': 1,
            'recurrency_type': 'months',
            'invoice_line_ids': invoice_line_data
        })

        self.apply_vendor_cron()
        recurring_domain = [('type', '=', 'in_invoice'), ('state', '=', 'draft'), ('is_recurring_document', '=', True)]
        recurring_invoice_count = AccountInvoice.search_count(recurring_domain)
        # after executing crons for recurrent invoices verify that no invoices is auto generated if the recurrent invoice is in `draft` state
        self.assertEquals(recurring_invoice_count, 0, 'Recurring invoices should not be generated when invoice is in `draft` state.')

        invoice.action_invoice_open()  # Validate invoice
        self.apply_vendor_cron()
        # After validating invoice ran cron and then checked, 2 recurring invoices should be generated
        recurring_invoice_count = previous_recurring_invoice_count = AccountInvoice.search_count(recurring_domain)
        self.assertEquals(recurring_invoice_count, 2, '2 recurring invoices should be generated.')

        purchase_journal.write({'update_posted': True})  # Allow to cancel the invoice
        invoice.action_invoice_cancel()  # Cancel the invoice
        self.apply_vendor_cron()
        # verify that invoices isn't generated if invoice is in `cancel` state
        recurring_invoice_count = AccountInvoice.search_count(recurring_domain)
        self.assertEquals(previous_recurring_invoice_count, recurring_invoice_count, 'Recurring invoices should not be generated when invoice is in `cancel` state.')

    def test_create_recurring_journal_entries(self):
        AccountMove = self.env['account.move']
        purchase_journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
        receivable_account_id = self.env['account.account'].search([('internal_type', '=', 'receivable')], limit=1).id

        # Create a move dated 5 days before today
        move = AccountMove.create({
                'name': '/',
                'journal_id': purchase_journal.id,
                'date': datetime.today() + relativedelta(days=-5),
                'line_ids': [(0, 0, {
                        'name': 'foo',
                        'debit': 50,
                        'account_id': receivable_account_id,
                    }), (0, 0, {
                        'name': 'bar',
                        'credit': 50,
                        'account_id': receivable_account_id,
                })],
                'is_recurrency_enabled': True,
                'recurrency_interval': 1,
                'recurrency_type': 'days',
            })

        self.apply_journal_entries_cron()
        recurring_domain = [('state', '=', 'draft'), ('is_recurring_document', '=', True)]
        recurring_move_count = AccountMove.search_count(recurring_domain)
        self.assertEquals(recurring_move_count, 0, 'Recurring journal entries should not be generated when it is in `draft` state.')

        move.post()  # Post the entries
        self.apply_journal_entries_cron()
        recurring_move_count = previous_move_count = AccountMove.search_count(recurring_domain)
        self.assertEquals(recurring_move_count, 5, '5 recurring journal entries should be generated.')

        purchase_journal.write({'update_posted': True})  # Allow to cancel the entries
        move.button_cancel()  # Cancel the entries
        self.apply_journal_entries_cron()
        # After cancelling the move rechecking if new moves are generated after executing cron
        recurring_move_count = AccountMove.search_count(recurring_domain)
        self.assertEquals(previous_move_count, recurring_move_count, 'Recurring journal entry should not be generated when it is in `cancel` state.')
