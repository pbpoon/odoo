# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        result = super(SaleOrder, self).action_confirm()
        for order in self:
            order.order_line.sudo()._purchase_service_generation()
        return result


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.multi
    def _purchase_service_prepare_order_values(self, supplierinfo):
        self.ensure_one()
        partner_supplier = supplierinfo.name
        fiscal_position_id = self.env['account.fiscal.position'].sudo().with_context(company_id=self.company_id.id).get_fiscal_position(partner_supplier.id)
        date_order = date.today() + relativedelta(days=self.customer_lead or 0) - relativedelta(days=int(supplierinfo.delay))  # SO confirm date + customer lead time (SOL) - supplier delay
        return {
            'partner_id': partner_supplier.id,
            'partner_ref': partner_supplier.ref,
            'company_id': self.company_id.id,
            'currency_id': partner_supplier.property_purchase_currency_id.id or self.env.user.company_id.currency_id.id,
            'dest_address_id': self.order_id.partner_shipping_id.id,
            'origin': self.order_id.name,
            'payment_term_id': partner_supplier.property_supplier_payment_term_id.id,
            'date_order': date_order,
            'fiscal_position_id': fiscal_position_id,
        }

    @api.multi
    def _purchase_service_prepare_line_values(self, purchase_order):
        self.ensure_one()
        purchase_qty_uom = self.product_uom._compute_quantity(self.product_uom_qty, self.product_id.uom_po_id)
        # determine vendor (real supplier, sharing the same partner as the one from the PO, but with more accurate informations like validity, quantity, ...)
        # Note: one partner can have multiple supplier info for the same product
        supplierinfo = self.product_id._select_seller(
            partner_id=purchase_order.partner_id,
            quantity=purchase_qty_uom,
            date=purchase_order.date_order and purchase_order.date_order[:10],
            uom_id=self.product_id.uom_po_id
        )
        fpos = purchase_order.fiscal_position_id
        taxes = fpos.map_tax(self.product_id.supplier_taxes_id) if fpos else self.product_id.supplier_taxes_id
        if taxes:
            taxes = taxes.filtered(lambda t: t.company_id.id == self.company_id.id)
        # compute unit price
        price_unit = 0.0
        if supplierinfo:
            price_unit = self.env['account.tax'].sudo()._fix_tax_included_price_company(supplierinfo.price, self.product_id.supplier_taxes_id, taxes, self.company_id)
            if purchase_order.currency_id and supplierinfo.currency_id != purchase_order.currency_id:
                price_unit = supplierinfo.currency_id.compute(price_unit, purchase_order.currency_id)
        # purchase line description in supplier lang
        product_in_supplier_lang = self.product_id.with_context({
            'lang': supplierinfo.name.lang,
            'partner_id': supplierinfo.name.id,
        })
        name = '[%s] %s' % (self.product_id.default_code, product_in_supplier_lang.display_name)
        if product_in_supplier_lang.description_purchase:
            name += '\n' + product_in_supplier_lang.description_purchase

        return {
            'name': '[%s] %s' % (self.product_id.default_code, self.name),
            'product_qty': purchase_qty_uom,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_po_id.id,
            'price_unit': price_unit,
            'date_planned': fields.Date.from_string(purchase_order.date_order) + relativedelta(days=int(supplierinfo.delay)),
            'taxes_id': [(6, 0, taxes.ids)],
            'order_id': purchase_order.id,
        }

    @api.multi
    def _purchase_service_generation(self):
        PurchaseOrder = self.env['purchase.order']
        supplier_po_map = {}
        for line in self:
            if line.product_id.service_to_purchase:

                # determine vendor of the order (take the first matching company and product)
                suppliers = line.product_id.seller_ids.filtered(lambda vendor: (not vendor.company_id or vendor.company_id == line.company_id) and (not vendor.product_id or vendor.product_id == line.product_id))
                if not suppliers:
                    raise UserError(_('There is no vendor associated to the product %s. Please define a vendor for this product.') % (line.product_id.display_name,))
                supplierinfo = suppliers[0]
                partner_supplier = supplierinfo.name  # yes, this field is not explicit ....

                # determine (or create) PO
                purchase_order = supplier_po_map.get(partner_supplier.id)
                if not purchase_order:
                    purchase_order = PurchaseOrder.search([
                        ('partner_id', '=', partner_supplier.id),
                        ('state', '=', 'draft'),
                    ], limit=1)
                if not purchase_order:
                    values = line._purchase_service_prepare_order_values(supplierinfo)
                    purchase_order = PurchaseOrder.create(values)
                    supplier_po_map[partner_supplier.id] = purchase_order
                else:  # update origin of existing PO
                    so_name = line.order_id.name
                    origins = []
                    if purchase_order.origin:
                        origins = purchase_order.origin.split(', ') + origins
                    if so_name not in origins:
                        origins += [so_name]
                        purchase_order.write({
                            'origin': ', '.join(origins)
                        })

                # add a PO line to the PO
                values = self._purchase_service_prepare_line_values(purchase_order)
                self.env['purchase.order.line'].create(values)
