# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class ProfitabilityAnalysis(models.Model):

    _name = "project.profitability.report.analysis"
    _description = "Project Profitability Analysis"
    _order = 'project_id, sale_line_id'
    _auto = False

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', readonly=True)
    project_id = fields.Many2one('project.project', string='Project', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Project Currency', readonly=True)
    company_id = fields.Many2one('res.company', string='Project Company', readonly=True)
    user_id = fields.Many2one('res.users', string='Project Manager', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    # cost
    timesheet_unit_amount = fields.Float("Timesheet Unit Amount", digits=(16, 2), readonly=True, group_operator="sum")
    timesheet_cost = fields.Float("Timesheet Cost", digits=(16, 2), readonly=True, group_operator="sum")
    # sale revenue
    date_order = fields.Datetime('Sales Order Confirmation Date', readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    amount_untaxed_to_invoice = fields.Float("Untaxed Amout To Invoice", digits=(16, 2), readonly=True, group_operator="sum")
    amount_untaxed_invoiced = fields.Float("Untaxed Amout Invoiced", digits=(16, 2), readonly=True, group_operator="sum")

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        query = """
            CREATE VIEW %s AS (
                WITH currency_rate as (%s)
                SELECT
                    min(TS.id) AS id,
                    P.id AS project_id,
                    P.user_id AS user_id,
                    AA.id AS analytic_account_id,
                    AA.partner_id AS partner_id,
                    C.id AS company_id,
                    C.currency_id AS currency_id,
                    S.id AS sale_order_id,
                    S.date_order AS date_order,
                    SOL.id AS sale_line_id,
                    SOL.product_id AS product_id,
                    (SOL.price_reduce / COALESCE(CR.rate, 1.0)) * SOL.qty_to_invoice AS amount_untaxed_to_invoice,
                    (SOL.price_reduce / COALESCE(CR.rate, 1.0)) * SOL.qty_invoiced AS amount_untaxed_invoiced,
                    SUM(TS.unit_amount) AS timesheet_unit_amount,
                    SUM(TS.amount) AS timesheet_cost
                FROM project_project P
                    JOIN account_analytic_account AA ON P.analytic_account_id = AA.id
                    JOIN res_company C ON C.id = AA.company_id
                    JOIN project_task T ON T.project_id = P.id
                    LEFT JOIN sale_order_line SOL ON T.sale_line_id = SOL.id
                    LEFT JOIN account_analytic_line TS ON TS.task_id = T.id AND TS.project_id IS NOT NULL
                    LEFT JOIN sale_order S ON SOL.order_id = S.id
                    LEFT JOIN currency_rate CR ON (CR.currency_id = SOL.currency_id
                        AND CR.currency_id != C.currency_id
                        AND CR.company_id = SOL.company_id
                        AND CR.date_start <= coalesce(S.date_order, now())
                        AND (CR.date_end IS NULL OR cr.date_end > coalesce(S.date_order, now())))
                GROUP BY C.id, P.id, AA.id, SOL.id, S.id, CR.rate
            )
        """ % (self._table, self.env['res.currency']._select_companies_rates())
        self._cr.execute(query)
