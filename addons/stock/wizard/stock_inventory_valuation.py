# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockInventoryValuation(models.TransientModel):
    _name = 'stock.inventory.valuation'
    _description = 'Inventory Valuation'

    product_name = fields.Char()

    def action_confirm(self):
        return self.env['stock.immediate.transfer'].browse(self._context.get('active_id')).process()
