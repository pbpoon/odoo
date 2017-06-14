# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.stock.tests.common import TestStockCommon


class TestPickShip(TestStockCommon):
    def create_pick_ship(self):
        picking_client = self.env['stock.picking'].create({
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
            'partner_id': self.partner_delta_id,
            'picking_type_id': self.picking_type_out,
        })

        dest = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 10,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_client.id,
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
            'state': 'waiting',
        })
        
        picking_pick = self.env['stock.picking'].create({
            'location_id': self.stock_location,
            'location_dest_id': self.pack_location,
            'partner_id': self.partner_delta_id,
            'picking_type_id': self.picking_type_out,
        })

        self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 10,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_pick.id,
            'location_id': self.stock_location,
            'location_dest_id': self.pack_location,
            'move_dest_ids': [(4, dest.id)],
            'state': 'confirmed',
        })
        return picking_pick, picking_client

    def test_mto_moves(self):
        """
            10 in stock, do pick->ship and check ship is assigned when pick is done, then backorder of ship
        """
        picking_pick, picking_client = self.create_pick_ship()
        location = self.env['stock.location'].browse(self.stock_location)

        # make some stock
        self.env['stock.quant'].increase_available_quantity(self.productA, location, 10.0)
        picking_pick.action_assign()
        picking_pick.move_lines[0].pack_operation_ids[0].qty_done = 10.0
        picking_pick.do_transfer()

        self.assertEqual(picking_client.state, 'assigned', 'The state of the client should be assigned')

        # Now partially transfer the ship
        picking_client.move_lines[0].pack_operation_ids[0].qty_done = 5
        picking_client.do_transfer() # no new in order to create backorder

        backorder = self.env['stock.picking'].search([('backorder_id', '=', picking_client.id)])
        self.assertEqual(backorder.state, 'assigned', 'Backorder should be started')

    def test_mto_moves_transfer(self):
        """
            10 in stock, 5 in pack.  Make sure it does not assign the 5 pieces in pack
        """
        picking_pick, picking_client = self.create_pick_ship()
        stock_location = self.env['stock.location'].browse(self.stock_location)
        self.env['stock.quant'].increase_available_quantity(self.productA, stock_location, 10.0)
        pack_location = self.env['stock.location'].browse(self.pack_location)
        self.env['stock.quant'].increase_available_quantity(self.productA, pack_location, 5.0)

        self.assertEqual(len(self.env['stock.quant']._gather(self.productA, stock_location)), 1.0)
        self.assertEqual(len(self.env['stock.quant']._gather(self.productA, pack_location)), 1.0)

        (picking_pick + picking_client).action_assign()

        move_pick = picking_pick.move_lines
        move_cust = picking_client.move_lines
        self.assertEqual(move_pick.state, 'assigned')
        self.assertEqual(picking_pick.state, 'assigned')
        self.assertEqual(move_cust.state, 'waiting')
        self.assertEqual(picking_client.state, 'waiting', 'The picking should not assign what it does not have')
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, stock_location), 0.0)
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 5.0)

        move_pick.pack_operation_ids[0].qty_done = 10.0
        picking_pick.do_transfer()

        self.assertEqual(move_pick.state, 'done')
        self.assertEqual(picking_pick.state, 'done')
        self.assertEqual(move_cust.state, 'assigned')
        self.assertEqual(picking_client.state, 'assigned', 'The picking should not assign what it does not have')
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, stock_location), 0.0)
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 5.0)
        self.assertEqual(len(self.env['stock.quant']._gather(self.productA, stock_location)), 0.0)
        self.assertEqual(len(self.env['stock.quant']._gather(self.productA, pack_location)), 1.0)

    def test_mto_moves_return(self):
        picking_pick, picking_client = self.create_pick_ship()
        stock_location = self.env['stock.location'].browse(self.stock_location)
        self.env['stock.quant'].increase_available_quantity(self.productA, stock_location, 10.0)

        picking_pick.action_assign()
        picking_pick.move_lines[0].pack_operation_ids[0].qty_done = 10.0
        picking_pick.do_transfer()
        self.assertEqual(picking_pick.state, 'done')
        self.assertEqual(picking_client.state, 'assigned')

        # return a part of what we've done
        stock_return_picking = self.env['stock.return.picking']\
            .with_context(active_ids=picking_pick.ids, active_id=picking_pick.ids[0])\
            .create({})
        stock_return_picking.product_return_moves.quantity = 2.0 # Return only 2
        stock_return_picking_action = stock_return_picking.create_returns()
        return_pick = self.env['stock.picking'].browse(stock_return_picking_action['res_id'])
        return_pick.move_lines[0].pack_operation_ids[0].qty_done = 2.0
        return_pick.do_transfer()
        # the client picking should not be assigned anymore, as we returned partially what we took
        self.assertEqual(picking_client.state, 'confirmed')

    def test_no_backorder_1(self):
        """ Check the behavior of doing less than asked in the picking pick and chosing not to
        create a backorder. In this behavior, the second picking should obviously only be able to
        reserve what was brought, but its initial demand should stay the same and the system will
        ask the user will have to consider again if he wants to create a backorder or not.
        """
        picking_pick, picking_client = self.create_pick_ship()
        location = self.env['stock.location'].browse(self.stock_location)

        # make some stock
        self.env['stock.quant'].increase_available_quantity(self.productA, location, 10.0)
        picking_pick.action_assign()
        picking_pick.move_lines[0].pack_operation_ids[0].qty_done = 5.0

        # create a backorder
        picking_pick.do_transfer()
        picking_pick_backorder = self.env['stock.picking'].search([('backorder_id', '=', picking_pick.id)])
        self.assertEqual(picking_pick_backorder.state, 'assigned')
        self.assertEqual(picking_pick_backorder.pack_operation_ids.product_qty, 5.0)

        self.assertEqual(picking_client.state, 'partially_available')

        # cancel the backorder
        picking_pick_backorder.action_cancel()
        self.assertEqual(picking_client.state, 'partially_available')


class TestSinglePicking(TestStockCommon):
    def test_backorder_1(self):
        """ Check the good behavior of creating a backorder for an available stock move.
        """
        delivery_order = self.env['stock.picking'].create({
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
            'partner_id': self.partner_delta_id,
            'picking_type_id': self.picking_type_out,
        })
        self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 2,
            'product_uom': self.productA.uom_id.id,
            'picking_id': delivery_order.id,
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
        })

        # make some stock
        pack_location = self.env['stock.location'].browse(self.pack_location)
        self.env['stock.quant'].increase_available_quantity(self.productA, pack_location, 2)

        # assign
        delivery_order.action_confirm()
        delivery_order.action_assign()
        self.assertEqual(delivery_order.state, 'assigned')
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 0.0)

        # valid with backorder creation
        delivery_order.move_lines[0].pack_operation_ids[0].qty_done = 1
        delivery_order.do_transfer()
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 0.0)

        backorder = self.env['stock.picking'].search([('backorder_id', '=', delivery_order.id)])
        self.assertEqual(backorder.state, 'assigned')

    def test_backorder_2(self):
        """ Check the good behavior of creating a backorder for a partially available stock move.
        """
        delivery_order = self.env['stock.picking'].create({
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
            'partner_id': self.partner_delta_id,
            'picking_type_id': self.picking_type_out,
        })
        self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 2,
            'product_uom': self.productA.uom_id.id,
            'picking_id': delivery_order.id,
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
        })

        # make some stock
        pack_location = self.env['stock.location'].browse(self.pack_location)
        self.env['stock.quant'].increase_available_quantity(self.productA, pack_location, 1)

        # assign to partially available
        delivery_order.action_confirm()
        delivery_order.action_assign()
        self.assertEqual(delivery_order.state, 'partially_available')
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 0.0)

        # valid with backorder creation
        delivery_order.move_lines[0].pack_operation_ids[0].qty_done = 1
        delivery_order.do_transfer()
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 0.0)

        backorder = self.env['stock.picking'].search([('backorder_id', '=', delivery_order.id)])
        self.assertEqual(backorder.state, 'confirmed')

    def test_extra_move_1(self):
        """ Check the good behavior of creating an extra move in a delivery order. This usecase
        simulates the delivery of 2 item while the initial stock move had to move 1 and there's
        only 1 in stock.
        """
        delivery_order = self.env['stock.picking'].create({
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
            'partner_id': self.partner_delta_id,
            'picking_type_id': self.picking_type_out,
        })
        move1 = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 1,
            'product_uom': self.productA.uom_id.id,
            'picking_id': delivery_order.id,
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
        })

        # make some stock
        pack_location = self.env['stock.location'].browse(self.pack_location)
        self.env['stock.quant'].increase_available_quantity(self.productA, pack_location, 1)
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 1.0)

        # assign to available
        delivery_order.action_confirm()
        delivery_order.action_assign()
        self.assertEqual(delivery_order.state, 'assigned')
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 0.0)

        # valid with backorder creation
        delivery_order.move_lines[0].pack_operation_ids[0].qty_done = 2
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 0.0)
        delivery_order.with_context(debug=True).do_transfer()
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), -1.0)

        extra_move = delivery_order.move_lines - move1
        extra_move_line = extra_move.pack_operation_ids[0]

        # self.assertEqual(move1.product_qty, 1.0)
        # self.assertEqual(move1.quantity_done, 1.0)
        self.assertEqual(move1.reserved_availability, 1.0)
        self.assertEqual(move1.pack_operation_ids.product_qty, 1.0)  # should keep the reservation
        self.assertEqual(move1.pack_operation_ids.qty_done, 1.0)
        self.assertEqual(move1.state, 'done')

        self.assertEqual(extra_move.product_qty, 1.0)
        self.assertEqual(extra_move.quantity_done, 1.0)
        self.assertEqual(extra_move.reserved_availability, 0.0)
        self.assertEqual(extra_move_line.product_qty, 0.0)  # should not be able to reserve
        self.assertEqual(extra_move_line.qty_done, 1.0)
        self.assertEqual(extra_move.state, 'done')

    def test_extra_move_2(self):
        """ Check the good behavior of creating an extra move in a delivery order. This usecase
        simulates the delivery of 3 item while the initial stock move had to move 1 and there's
        only 1 in stock.
        """
        delivery_order = self.env['stock.picking'].create({
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
            'partner_id': self.partner_delta_id,
            'picking_type_id': self.picking_type_out,
        })
        move1 = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 1,
            'product_uom': self.productA.uom_id.id,
            'picking_id': delivery_order.id,
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location,
        })

        # make some stock
        pack_location = self.env['stock.location'].browse(self.pack_location)
        self.env['stock.quant'].increase_available_quantity(self.productA, pack_location, 1)
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 1.0)

        # assign to available
        delivery_order.action_confirm()
        delivery_order.action_assign()
        self.assertEqual(delivery_order.state, 'assigned')
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 0.0)

        # valid with backorder creation
        delivery_order.move_lines[0].pack_operation_ids[0].qty_done = 3
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), 0.0)
        delivery_order.with_context(debug=True).do_transfer()
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, pack_location), -2.0)

        extra_move = delivery_order.move_lines - move1
        extra_move_line = extra_move.pack_operation_ids[0]

        self.assertEqual(move1.product_qty, 1.0)
        self.assertEqual(move1.quantity_done, 1.0)
        self.assertEqual(move1.reserved_availability, 1.0)
        self.assertEqual(move1.pack_operation_ids.product_qty, 1.0)  # should keep the reservation
        self.assertEqual(move1.pack_operation_ids.qty_done, 1.0)
        self.assertEqual(move1.state, 'done')

        self.assertEqual(extra_move.product_qty, 2.0)
        self.assertEqual(extra_move.quantity_done, 2.0)
        self.assertEqual(extra_move.reserved_availability, 0.0)
        self.assertEqual(extra_move_line.product_qty, 0.0)  # should not be able to reserve
        self.assertEqual(extra_move_line.qty_done, 2.0)
        self.assertEqual(extra_move.state, 'done')

    def test_extra_move_3(self):
        """ Check the good behavior of creating an extra move in a receipt. This usecase simulates
         the receipt of 2 item while the initial stock move had to move 1.
        """
        receipt = self.env['stock.picking'].create({
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'partner_id': self.partner_delta_id,
            'picking_type_id': self.picking_type_in,
        })
        move1 = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 1,
            'product_uom': self.productA.uom_id.id,
            'picking_id': receipt.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
        })
        stock_location = self.env['stock.location'].browse(self.stock_location)

        # assign to available
        receipt.action_confirm()
        receipt.action_assign()
        self.assertEqual(receipt.state, 'assigned')

        # valid with backorder creation
        receipt.move_lines[0].pack_operation_ids[0].qty_done = 2
        receipt.with_context(debug=True).do_transfer()
        self.assertEqual(self.env['stock.quant'].get_available_quantity(self.productA, stock_location), 2.0)

        extra_move = receipt.move_lines - move1
        extra_move_line = extra_move.pack_operation_ids[0]

        self.assertEqual(move1.product_qty, 1.0)
        self.assertEqual(move1.quantity_done, 1.0)
        self.assertEqual(move1.reserved_availability, 1.0)
        self.assertEqual(move1.pack_operation_ids.product_qty, 1.0)  # should keep the reservation
        self.assertEqual(move1.pack_operation_ids.qty_done, 1.0)
        self.assertEqual(move1.state, 'done')

        self.assertEqual(extra_move.product_qty, 1.0)
        self.assertEqual(extra_move.quantity_done, 1.0)
        self.assertEqual(extra_move.reserved_availability, 0.0)
        self.assertEqual(extra_move_line.product_qty, 0.0)  # should not be able to reserve
        self.assertEqual(extra_move_line.qty_done, 1.0)
        self.assertEqual(extra_move.state, 'done')