# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo import api, fields, models, _


class AccountFiscalYear(models.Model):
    _name = 'account.fiscalyear'
    _description = 'Fiscal Year'

    name = fields.Char(string='Name', required=True,
        help='The name of your fiscal year.')
    date_start = fields.Date(string='Start Date', required=True,
        help='Starting date.')
    date_end = fields.Date(string='End Date', required=True,
        help='The ending date is inclusive to your fiscal year.')
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.user.company_id)

    @api.constrains('date_start', 'date_end', 'company_id')
    def _check_dates(self):
        for fy in self:
            domain = [
                ('id', '!=', fy.id),
                ('company_id', '=', fy.company_id.id),
                '|',
                '&', ('date_start', '<=', fy.date_start), ('date_end', '>=', fy.date_start),
                '&', ('date_start', '<=', fy.date_end), ('date_end', '>=', fy.date_end)
            ]

            if self.search_count(domain) > 0:
                raise ValidationError(_('You can not have an overlap between two fiscal years, please correct the start and/or end dates of your fiscal years.'))
