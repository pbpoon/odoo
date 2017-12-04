# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class WizardMultiChartsAccounts(models.TransientModel):
    _inherit = 'wizard.multi.charts.accounts'

    @api.multi
    def execute(self):
        res = super(WizardMultiChartsAccounts, self).execute()

        # Search for installed acquirers modules
        acquirer_modules = self.env['ir.module.module'].search(
            [('name', 'like', 'payment_%'), ('state', '=', 'installed')])
        acquirer_names = [a.name.split('_')[1] for a in acquirer_modules]

        # Search for acquirers having no journal
        acquirers = self.env['payment.acquirer'].search(
            [('provider', 'in', acquirer_names), ('journal_id', '=', False), ('company_id', '=', self.company_id.id)])

        # Try to generate the missing journals
        acquirers.try_loading_for_acquirer()
        return res
