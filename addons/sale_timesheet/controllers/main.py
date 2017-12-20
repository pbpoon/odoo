# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http, _
from odoo.http import request
from odoo.osv import expression

from odoo.tools import float_round


class SaleTimesheetController(http.Controller):

    @http.route('/timesheet/plan', type='json', auth="user")
    def plan(self, domain):
        """ Get the HTML of the project plan for projects matching the given domain
            :param domain: a domain for project.project
        """
        values = self._prepare_plan_values(domain)
        view = request.env.ref('sale_timesheet.timesheet_plan')
        return {
            'html_content': view.render(values)
        }

    def _prepare_plan_values(self, domain):

        projects = request.env['project.project'].search(domain)
        currency = request.env.user.company_id.currency_id
        hour_rounding = request.env.ref('product.product_uom_hour').rounding
        billable_types = ['non_billable', 'non_billable_project', 'billable_time', 'billable_fixed']

        values = {
            'projects': projects,
            'currency': currency,
            'domain': domain,
            'timesheet_domain': [('project_id', 'in', projects.ids)],
            'stat_buttons': self._plan_get_stat_button(projects),
        }

        #
        # Hours, Rates and Profitability
        #
        dashboard_values = {
            'hours': dict.fromkeys(billable_types + ['total'], 0.0),
            'rates': dict.fromkeys(billable_types + ['total'], 0.0),
            'profit': {
                'invoiced': 0.0,
                'to_invoiced': 0.0,
                'cost': 0.0,
                'total': 0.0,
            }
        }

        # hours (from timesheet) and rates (by billable type)
        dashboard_domain = [('project_id', 'in', projects.ids), ('timesheet_invoice_type', '!=', False)]  # force billable type
        dashboard_data = request.env['account.analytic.line'].read_group(dashboard_domain, ['unit_amount', 'timesheet_revenue', 'timesheet_invoice_type'], ['timesheet_invoice_type'])
        dashboard_total_hours = sum([data['unit_amount'] for data in dashboard_data])
        for data in dashboard_data:
            billable_type = data['timesheet_invoice_type']
            dashboard_values['hours'][billable_type] = float_round(data.get('unit_amount'), precision_rounding=hour_rounding)
            dashboard_values['hours']['total'] += float_round(data.get('unit_amount'), precision_rounding=hour_rounding)
            dashboard_values['rates'][billable_type] = round(data.get('unit_amount') / dashboard_total_hours * 100, 2)
            dashboard_values['rates']['total'] += round(data.get('unit_amount') / dashboard_total_hours * 100, 2)

        # profitability, using profitability SQL report
        profit = dict.fromkeys(['invoiced', 'to_invoice', 'cost', 'total'], 0.0)
        profitability_raw_data = request.env['project.profitability.report.analysis'].read_group([('project_id', 'in', projects.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_cost'], ['project_id'])
        for data in profitability_raw_data:
            profit['invoiced'] += data.get('amount_untaxed_invoiced', 0.0)
            profit['to_invoice'] += data.get('amount_untaxed_to_invoice', 0.0)
            profit['cost'] += data.get('timesheet_cost', 0.0)
        profit['total'] = sum([profit[item] for item in profit.keys()])
        dashboard_values['profit'] = profit

        values['dashboard'] = dashboard_values

        #
        # Time Repartition (per employee per billable types)
        #
        repartition_domain = [('project_id', 'in', projects.ids), ('employee_id', '!=', False), ('timesheet_invoice_type', '!=', False)]  # force billable type
        repartition_data = request.env['account.analytic.line'].read_group(repartition_domain, ['employee_id', 'timesheet_invoice_type', 'unit_amount'], ['employee_id', 'timesheet_invoice_type'], lazy=False)

        # set repartition per type per employee
        repartition_employee = {}
        for data in repartition_data:
            employee_id = data['employee_id'][0]
            repartition_employee.setdefault(employee_id, dict(
                employee_id=data['employee_id'][0],
                employee_name=data['employee_id'][1],
                non_billable_project=0.0,
                non_billable=0.0,
                billable_time=0.0,
                billable_fixed=0.0,
                total=0.0,
            ))[data['timesheet_invoice_type']] = float_round(data.get('unit_amount', 0.0), precision_rounding=hour_rounding)
            repartition_employee[employee_id]['__domain_' + data['timesheet_invoice_type']] = data['__domain']

        # compute total
        for employee_id, vals in repartition_employee.items():
            repartition_employee[employee_id]['total'] = sum([vals[inv_type] for inv_type in billable_types])

        hours_per_employee = [repartition_employee[employee_id]['total'] for employee_id in repartition_employee]
        values['repartition_employee_max'] = max(hours_per_employee) if hours_per_employee else 1
        values['repartition_employee'] = repartition_employee

        return values

    def _plan_get_stat_button(self, projects):
        stat_buttons = []
        stat_buttons.append({
            'name': _('Timesheets'),
            'res_model': 'account.analytic.line',
            'domain': [('project_id', 'in', ('project_id', 'in', projects.ids))],
            'icon': 'fa fa-calendar',
        })
        stat_buttons.append({
            'name': _('Tasks'),
            'count': sum(projects.mapped('task_count')),
            'res_model': 'project.task',
            'domain': [('project_id', 'in', ('project_id', 'in', projects.ids))],
            'icon': 'fa fa-tasks',
        })
        return stat_buttons

    @http.route('/timesheet/plan/action', type='json', auth="user")
    def plan_stat_button(self, domain, res_model='account.analytic.line'):
        action = {
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'list',
            'domain': domain,
        }
        if res_model == 'account.analytic.line':
            ts_view_tree_id = request.env.ref('hr_timesheet.hr_timesheet_line_tree').id
            ts_view_form_id = request.env.ref('hr_timesheet.hr_timesheet_line_form').id
            action = {
                'name': _('Timesheets'),
                'type': 'ir.actions.act_window',
                'res_model': res_model,
                'view_mode': 'tree,form',
                'view_type': 'tree',
                'views': [[ts_view_tree_id, 'list'], [ts_view_form_id, 'form']],
                'domain': domain,
            }
        elif res_model == 'project.task':
            action = request.env.ref('project.action_view_task').read()[0]
            action.update({
                'name': _('Tasks'),
                'domain': domain,
                'context': request.env.context,  # erase original context to avoid default filter
            })
        return action
