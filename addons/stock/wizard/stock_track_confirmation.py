# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, tools


class StockTrackConfirmation(models.TransientModel):
    _name = 'stock.track.confirmation'

    track_products = fields.Char()
    inventory_id = fields.Many2one('stock.inventory')

    @api.one
    def action_confirm(self):
        return self.inventory_id.action_done()
