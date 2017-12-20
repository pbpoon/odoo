# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from odoo import fields
from odoo.tests import common


class TestSaleExpectedDate(common.TransactionCase):

    def test_sale_order_expected_date(self):
        """ Test expected date and effective date of Sales Orders """
        Product = self.env['product.product']

        product_A = Product.create({
            'name': 'Product A',
            'type': 'product',
            'sale_delay': 5,
        })
        product_B = Product.create({
            'name': 'Product B',
            'type': 'product',
            'sale_delay': 10,
        })
        product_C = Product.create({
            'name': 'Product C',
            'type': 'product',
            'sale_delay': 15,
        })
        sale_order = self.env['sale.order'].create({
            'partner_id': self.ref('base.res_partner_3'),
            'picking_policy': 'direct',
            'order_line': [
                (0, 0, {'name': product_A.name, 'product_id': product_A.id, 'customer_lead': product_A.sale_delay}),
                (0, 0, {'name': product_B.name, 'product_id': product_B.id, 'customer_lead': product_B.sale_delay}),
                (0, 0, {'name': product_C.name, 'product_id': product_C.id, 'customer_lead': product_C.sale_delay})
            ],
        })

        current_date = fields.Datetime.from_string(fields.Datetime.now())

        # if Shipping Policy is set to `direct`(when SO is in draft state) then expected date should be
        # current date + shortest lead time from all of it's order lines
        expect_date = fields.Datetime.to_string(current_date + timedelta(days=5))
        self.assertEquals(expect_date, sale_order.expected_date, "Wrong expected date on sale order!")

        # if Shipping Policy is set to `one`(when SO is in draft state) then expected date should be
        # current date + longest lead time from all of it's order lines
        sale_order.write({'picking_policy': 'one'})
        expect_date = fields.Datetime.to_string(current_date + timedelta(days=15))
        self.assertEquals(expect_date, sale_order.expected_date, "Wrong expected date on sale order!")

        sale_order.action_confirm()

        # Setting confirmation date of SO to 5 days from today so that the expected/effective date could be checked
        # against real confirmation date
        confirm_date = current_date + timedelta(5)
        sale_order.write({'confirmation_date': confirm_date})

        # if Shipping Policy is set to `one`(when SO is confirmed) then expected date should be
        # SO confirmation date + longest lead time from all of it's order lines
        expect_date = fields.Datetime.to_string(confirm_date + timedelta(days=15))
        self.assertEquals(expect_date, sale_order.expected_date, "Wrong expected date on sale order!")

        # if Shipping Policy is set to `direct`(when SO is confirmed) then expected date should be
        # SO confirmation date + shortest lead time from all of it's order lines
        sale_order.write({'picking_policy': 'direct'})
        expect_date = fields.Datetime.to_string(confirm_date + timedelta(days=5))
        self.assertEquals(expect_date, sale_order.expected_date, "Wrong expected date on sale order!")

        # Check effective date, it should be date on which the first shipment successfully delivered to customer
        picking = sale_order.picking_ids[0]
        self.env['stock.immediate.transfer'].create({'pick_ids': [(4,picking.id)]}).process()
        self.assertEquals(picking.state, "done", "Picking not processed correctly!")
        self.assertEquals(fields.Date.today(), sale_order.effective_date, "Wrong effective date on sale order!")
