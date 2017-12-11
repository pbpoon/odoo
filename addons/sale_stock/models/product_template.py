# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.onchange('type')
    def _onchange_type(self):
        super(ProductTemplate, self)._onchange_type()
        if self.type == 'product':
            self.expense_policy = 'no'
            self.service_type = 'manual'
