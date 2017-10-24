# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class Digest(models.Model):
    _inherit = 'digest.digest'

    kpi_hr_recruitment_new_colleagues = fields.Boolean(string='New Employees')
    kpi_hr_recruitment_new_colleagues_value = fields.Integer(compute='_compute_kpi_hr_recruitment_new_colleagues_value')

    @api.depends('start_date', 'end_date')
    def _compute_kpi_hr_recruitment_new_colleagues_value(self):
        for record in self:
            new_colleagues = self.env['hr.employee'].search_count([("create_date", ">=", self.start_date),
                                                                   ("create_date", "<", self.end_date)])
            record.kpi_hr_recruitment_new_colleagues_value = new_colleagues
