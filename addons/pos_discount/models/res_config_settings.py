# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    discount_pc = fields.Float(string='Discount Percentage', related='company_id.discount_pc', help='The default discount percentage')
    discount_product_id = fields.Many2one('product.product', string='Discount Product', domain="[('available_in_pos', '=', True)]", help='The product used to model the discount.', related='company_id.discount_product_id')
