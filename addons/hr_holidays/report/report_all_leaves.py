# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class LeaveAllReport(models.Model):

    _name = "report.hr_holidays.report_leave_all"
    _auto = False

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    name = fields.Char('Description', readonly=True)
    number_of_days = fields.Float('Number of Days', readonly=True)
    type = fields.Selection([
        ('allocation', 'Allocation Request'),
        ('request', 'Leave Request')
        ], string='Request Type', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    category_id = fields.Many2one('hr.employee.category', string='Employee Tag', readonly=True)
    holiday_status_id = fields.Many2one("leave.type", string="Leave Type", readonly=True)
    state = fields.Selection([
        ('draft', 'To Submit'),
        ('cancel', 'Cancelled'),
        ('confirm', 'To Approve'),
        ('refuse', 'Refused'),
        ('validate1', 'Second Approval'),
        ('validate', 'Approved')
        ], string='Status', readonly=True)
    holiday_type = fields.Selection([
        ('employee', 'By Employee'),
        ('category', 'By Employee Tag')
    ], string='Allocation Mode', readonly=True)
    date_from = fields.Datetime('Start Date', readonly=True)
    date_to = fields.Datetime('End Date', readonly=True)
    payslip_status = fields.Boolean('Reported in last payslips', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'report_hr_holidays_report_leave_all')
        self._cr.execute("""
            CREATE or REPLACE view report_hr_holidays_report_leave_all as (
                SELECT row_number() over(ORDER BY leaves.employee_id) as id,
                leaves.employee_id as employee_id, leaves.name as name,
                leaves.number_of_days as number_of_days, leaves.type as type,
                leaves.category_id as category_id, leaves.department_id as department_id,
                leaves.holiday_status_id as holiday_status_id, leaves.state as state,
                leaves.holiday_type as holiday_type, leaves.date_from as date_from,
                leaves.date_to as date_to, leaves.payslip_status as payslip_status
                from (select
                    allocation.employee_id as employee_id,
                    allocation.name as name,
                    allocation.number_of_days as number_of_days,
                    allocation.category_id as category_id,
                    allocation.department_id as department_id,
                    allocation.holiday_status_id as holiday_status_id,
                    allocation.state as state,
                    allocation.holiday_type,
                    null as date_from,
                    null as date_to,
                    FALSE as payslip_status,
                    'allocation' as type
                from leave_allocation as allocation
                union select
                    request.employee_id as employee_id,
                    request.name as name,
                    request.number_of_days as number_of_days,
                    request.category_id as category_id,
                    request.department_id as department_id,
                    request.holiday_status_id as holiday_status_id,
                    request.state as state,
                    request.holiday_type,
                    request.date_from as date_from,
                    request.date_to as date_to,
                    request.payslip_status as payslip_status,
                    'request' as type
                from leave_request as request) leaves
            );
        """)
