# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models

class MrpBomCost(models.AbstractModel):
    _name = 'report.mrp.mrp_bom_cost_report'

    def get_bom_cost(self, current_line, quantity):
        total = 0
        for child_line in current_line.child_line_ids:
            if child_line._skip_bom_line(current_line.product_id):
                continue
            line_quantity = (quantity / child_line.bom_id.product_qty) * child_line.product_qty
            if child_line.child_bom_id:
                line_quantity = child_line.product_uom_id._compute_quantity(line_quantity, child_line.child_bom_id.product_uom_id)
            total += self.get_bom_cost(child_line, line_quantity)
        if not current_line.child_bom_id:
            unit_price = current_line.product_id.uom_id._compute_price(current_line.product_id.standard_price, current_line.product_uom_id)
            total = unit_price * quantity
        return total

    def get_bom_lines(self, bom_lines, product, qty, parent_line, level):
        lines = []
        total = 0
        next_level = level + 1
        print_mode = self.env.context.get('print_mode')
        for bom_line in bom_lines:
            if bom_line._skip_bom_line(product):
                continue
            line_quantity = bom_line.product_qty
            if parent_line:
                qty = parent_line.product_uom_id._compute_quantity(qty, bom_line.bom_id.product_uom_id) / bom_line.bom_id.product_qty
                line_quantity = bom_line.product_qty * qty
            has_child = bom_line.child_line_ids and True or False
            unit_price = 0.0
            total_price = 0.0
            if has_child:
                qty = bom_line.product_uom_id._compute_quantity(line_quantity, bom_line.child_bom_id.product_uom_id)
                unit_price = self.get_bom_cost(bom_line, qty) / line_quantity
            else:
                unit_price = bom_line.product_id.uom_id._compute_price(bom_line.product_id.standard_price, bom_line.product_uom_id)
            total_price = line_quantity * unit_price
            lines.append(({
                'product_id': bom_line.product_id,
                'product_uom': bom_line.product_uom_id,
                'level': level,
                'price_unit': unit_price,
                'product_uom_qty': line_quantity,
                'total_price': total_price,
                'has_child': has_child,
                'print_mode': print_mode,
                'id': bom_line.id,
                'parent_id': parent_line and parent_line.id,
            }))
            if not parent_line:
                total += total_price
            for child_line in bom_line.child_line_ids:
                _, _lines = self.get_bom_lines(child_line, bom_line.product_id, line_quantity, bom_line, next_level)
                lines += _lines
        return total, lines

    @api.multi
    def get_lines(self, boms):
        product_lines = []
        for bom in boms:
            products = bom.product_id
            if not products:
                products = bom.product_tmpl_id.product_variant_ids
            for product in products:
                attributes = []
                for value in product.attribute_value_ids:
                    attributes += [(value.attribute_id.name, value.name)]
                product_line = {'bom': bom, 'name': product.display_name, 'lines': [], 'total': 0.0,
                                'currency': self.env.user.company_id.currency_id,
                                'product_uom_qty': bom.product_qty,
                                'product_uom': bom.product_uom_id,
                                'attributes': attributes, 'id': product.id}
                total, lines = self.get_bom_lines(bom.bom_line_ids, product, bom.product_qty, False, 0)
                product_line['lines'] = lines
                product_line['total'] = total
                product_lines += [product_line]
        return product_lines

    @api.model
    def get_report_values(self, docids, data=None):
        boms = self.env['mrp.bom'].browse(docids)
        res = self.get_lines(boms)
        return {'lines': res}
