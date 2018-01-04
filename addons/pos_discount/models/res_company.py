# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _get_default_discount_product(self):
        return self.env.ref('point_of_sale.product_product_consumable')

    discount_product_id = fields.Many2one('product.product', string='Discount Product', domain="[('available_in_pos', '=', True)]", help='The product used to model the discount.', default=_get_default_discount_product)
    discount_pc = fields.Float(string='Discount Percentage', default=10, help='The default discount percentage')

    @api.onchange('module_pos_discount')
    def _onchange_module_pos_discount(self):
        if self.module_pos_discount:
            self.discount_product_id = self.env['product.product'].search([('available_in_pos', '=', True)], limit=1)
            self.discount_pc = 10.0
        else:
            self.discount_product_id = False
            self.discount_pc = 0.0
