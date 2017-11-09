# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, exceptions, fields, models, _


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    manufacture_to_resupply = fields.Boolean(
        'Manufacture in this Warehouse', default=True,
        help="When products are manufactured, they can be manufactured in this warehouse.")
    manufacture_pull_id = fields.Many2one(
        'procurement.rule', 'Manufacture Rule')
    manu_type_id = fields.Many2one(
        'stock.picking.type', 'Manufacturing Operation Type',
        domain=[('code', '=', 'mrp_operation')])
    manufacture_steps = fields.Selection([
                                ('manu_only', 'Produce'),
                                ('pick_manu', 'Pick the components + Produce')],
                                'Manufacture', default='manu_only', required=True,
                                help="Produce : Move the raw materials to the production location directly and start the manufaturing process.\nPick / Produce : Unload the raw materials from the stock to Input location first, and then transfer it to the production location.")
    manu_mto_pull_id = fields.Many2one('procurement.rule', 'MTO rule')
    wh_input_manu_loc_id = fields.Many2one("stock.location", "Input Manufacture Location")
    multistep_manu_route_id = fields.Many2one('stock.location.route', 'Multistep Manufacturing Route', ondelete='restrict')

    def _create_or_update_locations(self):
        # This method is used to create/update locations of input type stock location.
        self.ensure_one()
        if not self.wh_input_manu_loc_id:
            self.wh_input_manu_loc_id = self.env['stock.location'].create({'name': _('PROD/IN'),
                                                             'usage': 'internal',
                                                             'location_id': self.view_location_id.id,
                                                             'company_id': self.company_id.id}).id
        self.wh_input_manu_loc_id.active = self.manufacture_to_resupply and self.manufacture_steps != 'manu_only'
        return True

    def _find_existing_push_rec(self, push_vals):
        self.ensure_one()
        push_rec = self.env['stock.location.path'].with_context(active_test=False).search([
                    ('location_from_id', '=', push_vals['location_from_id']),
                    ('location_dest_id', '=', push_vals['location_dest_id']),
                    ('picking_type_id', '=', push_vals['picking_type_id']),
                    ('warehouse_id', '=', self.id),
                    ('route_id', '=', push_vals['route_id'])
                ])
        return push_rec

    def _find_existing_pull_rec(self, pull_vals):
        self.ensure_one()
        pull_rec = self.env['procurement.rule'].with_context(active_test=False).search([
                    ('location_src_id', '=', pull_vals['location_src_id']),
                    ('location_id', '=', pull_vals['location_id']),
                    ('picking_type_id', '=', pull_vals['picking_type_id']),
                    ('warehouse_id', '=', self.id),
                    ('route_id', '=', pull_vals['route_id'])
                ])
        return pull_rec

    def _create_or_update_manufacturing_route(self):
        # This method is used to update values related to manufacturing route,
        # and if warehouse is not having any manufacturing route, this method will create.
        manufacture_route_id = self._get_manufacture_route_id()
        pick_routings = [self.Routing(self.wh_input_manu_loc_id, self.lot_stock_id, self.int_type_id)]
        push_vals_list, pull_rules_list = self._get_push_pull_rules_values(
            pick_routings, values={'active': True, 'procure_method': 'make_to_order', 'route_id': manufacture_route_id})
        StockLocationPath = self.env['stock.location.path']
        ProcurementRule = self.env['procurement.rule']
        for push_vals in push_vals_list:
            existing_push = self._find_existing_push_rec(push_vals)
            if not existing_push:
                vals = {
                    'name': push_vals['name'],
                    'active': False,
                    'location_from_id': push_vals['location_from_id'],
                    'location_dest_id': push_vals['location_dest_id'],
                    'picking_type_id': push_vals['picking_type_id'],
                    'warehouse_id': self.id,
                    'route_id': manufacture_route_id
                }
                StockLocationPath.create(vals)
        for pull_vals in pull_rules_list:
            existing_pull = self._find_existing_pull_rec(pull_vals)
            if not existing_pull:
                pull_vals.update({'active': False})
                ProcurementRule.create(pull_vals)
        return True

    def _create_or_update_manufacturing_picking_types(self):
        self.ensure_one()
        PickingType = self.env['stock.picking.type']
        Sequence = self.env['ir.sequence']
        location_id, location_dest_id = (self.lot_stock_id.id if self.manufacture_steps == 'manu_only' else self.wh_input_manu_loc_id.id,
            self.lot_stock_id.id)
        picking_types = {}
        # Create picking types if it does not exist else update its locations.
        if not self.manu_type_id:
            seq_id = Sequence.search([('code', '=', 'mrp.production')], limit=1)
            if not seq_id:
                seq_id = Sequence.sudo().create({'name': 'Production order',
                                                 'prefix': 'MO/',
                                                 'padding': 5})
            vals = {'active': self.manufacture_to_resupply,
                    'code': 'mrp_operation',
                    'default_location_dest_id': location_dest_id,
                    'default_location_src_id': location_id,
                    'sequence_id': seq_id.id,
                    'name': 'Manufacture', 'warehouse_id': self.id}
            picking_types.update({'manu_type_id': vals})
        else:
            self.manu_type_id.write({
                'active': self.manufacture_to_resupply,
                'default_location_dest_id': location_dest_id,
                'default_location_src_id': location_id})
        for field_name, values in picking_types.items():
            picking_types[field_name] = PickingType.create(values).id
        self.write(picking_types)
        return True

    def create_sequences_and_picking_types(self):
        res = super(StockWarehouse, self).create_sequences_and_picking_types()
        self._create_manufacturing_picking_type()
        return res

    @api.multi
    def get_routes_dict(self):
        result = super(StockWarehouse, self).get_routes_dict()
        for warehouse in self:
            result[warehouse.id]['manufacture'] = [self.Routing(warehouse.lot_stock_id, warehouse.lot_stock_id, warehouse.int_type_id)]
        return result

    @api.multi
    def _get_manufacturing_route_values(self, route_type):
        return {
            'name': self._format_routename(route_type=route_type),
            'product_categ_selectable': True,
            'company_id': self.company_id.id,
            'product_selectable': False,
            'sequence': 10,
        }

    def _get_manufacture_route_id(self):
        # This method will return manufacture route,
        # it will create manufacture rout if it does not exist.
        Route = self.env['stock.location.route']
        manufacture_route_id = self.env.ref('mrp.route_warehouse0_manufacture').id
        if not manufacture_route_id:
            manufacture_route_id = Route.search([('name', 'like', _('Manufacture'))], limit=1).id
        if not manufacture_route_id:
            manufacture_route_id = Route.create(self._get_manufacturing_route_values('manu_only')).id
        return manufacture_route_id

    def _get_manufacture_pull_rules_values(self, route_values):
        if not self.manu_type_id:
            self._create_manufacturing_picking_type()
        dummy, pull_rules_list = self._get_push_pull_rules_values(route_values, pull_values={
            'name': self._format_routename(_(' Manufacture')),
            'location_src_id': False,  # TDE FIXME
            'action': 'manufacture',
            'route_id': self._get_manufacture_route_id(),
            'picking_type_id': self.manu_type_id.id,
            'propagate': False,
            'active': True})
        return pull_rules_list

    def _create_manufacturing_picking_type(self):
        # TDE CLEANME
        picking_type_obj = self.env['stock.picking.type']
        seq_obj = self.env['ir.sequence']
        for warehouse in self:
            #man_seq_id = seq_obj.sudo().create('name': warehouse.name + _(' Sequence Manufacturing'), 'prefix': warehouse.code + '/MANU/', 'padding')
            wh_stock_loc = warehouse.lot_stock_id
            seq = seq_obj.search([('code', '=', 'mrp.production')], limit=1)
            other_pick_type = picking_type_obj.search([('warehouse_id', '=', warehouse.id)], order = 'sequence desc', limit=1)
            color = other_pick_type.color if other_pick_type else 0
            max_sequence = other_pick_type and other_pick_type.sequence or 0
            manu_type = picking_type_obj.create({
                'name': _('Manufacturing'),
                'warehouse_id': warehouse.id,
                'code': 'mrp_operation',
                'use_create_lots': True,
                'use_existing_lots': False,
                'sequence_id': seq.id,
                'default_location_src_id': wh_stock_loc.id,
                'default_location_dest_id': wh_stock_loc.id,
                'sequence': max_sequence,
                'color': color})
            warehouse.write({'manu_type_id': manu_type.id})

    def _create_or_update_manufacture_pull(self):
        self.ensure_one()
        location = self.lot_stock_id
        location_src = self.wh_input_manu_loc_id if self.manufacture_steps != 'manu_only' else self.lot_stock_id
        routings = [self.Routing(location, location_src, self.manu_type_id)]
        if self.manufacture_pull_id:
            manufacture_pull = self.manufacture_pull_id
            manufacture_pull.write({
                'location_id': location.id,
                'location_src_id': location_src.id,
                'picking_type_id': self.manu_type_id.id,
                'active': self.manufacture_to_resupply})
        else:
            routings = [self.Routing(location_src, location, self.manu_type_id)]
            dummy, pull_vals = self._get_push_pull_rules_values(routings, pull_values={
                                'name': self._format_routename(_(' Manufacture')),
                                'action': 'manufacture',
                                'route_id': self._get_manufacture_route_id(),
                                'propagate': False,
                                'active': self.manufacture_to_resupply})
            manufacture_pull = self.env['procurement.rule'].create(pull_vals[0])
        return manufacture_pull.id

    def _create_or_update_manufacturing_mto_pull(self):
        """ Create Manufacturing MTO procurement rule and link it to the generic MTO route """
        location_id = self.wh_input_manu_loc_id if self.manufacture_steps != 'manu_only' else self.env.ref('stock.location_production')
        picking_type_id = self.int_type_id
        routings = [self.Routing(self.lot_stock_id, location_id, picking_type_id)]
        if self.manu_mto_pull_id:
            self.manu_mto_pull_id.write(self._get_mto_pull_rules_values(routings)[0])
            return self.manu_mto_pull_id
        manu_mto_pull = self.env['procurement.rule'].create(self._get_mto_pull_rules_values(routings)[0])
        return manu_mto_pull

    def _get_route_name(self):
        names = super(StockWarehouse, self)._get_route_name()
        names.update({
                 'manu_only': _('Produce'),
                 'pick_manu': _('Pick/Produce')
               })
        return names

    def _create_or_update_additional_step_routes(self):
        """This method will create/update push/pull rules for new route of Manufacturing."""
        self.ensure_one()
        if self.multistep_manu_route_id:
            manufacture_route = self.multistep_manu_route_id
            manufacture_route.write({'name':  self._format_routename(route_type=self.manufacture_steps)})
            manufacture_route.pull_ids.write({'active': False})
            manufacture_route.push_ids.write({'active': False})
        else:
            route_vals = self._get_manufacturing_route_values(self.manufacture_steps)
            manufacture_route = self.env['stock.location.route'].create(route_vals)
        # procurement (pull) rules for new route
        production_location = self.env.ref('stock.location_production')
        self._create_or_update_manufacturing_picking_types()
        dummy, pull_rules_list1 = self._get_push_pull_rules_values(
            [self.Routing(self.lot_stock_id, self.wh_input_manu_loc_id, self.int_type_id)], values={'active': self.manufacture_steps != 'manu_only', 'route_id': manufacture_route.id},
            push_values=None, pull_values={'procure_method': 'make_to_stock'})
        dummy, pull_rules_list2 = self._get_push_pull_rules_values(
            [self.Routing(self.wh_input_manu_loc_id, production_location, self.int_type_id)], values={'active': self.manufacture_steps != 'manu_only', 'route_id': manufacture_route.id},
            push_values=None, pull_values={'procure_method': 'make_to_order'})
        for pull_vals in pull_rules_list1 + pull_rules_list2:
            existing_pull = self._find_existing_pull_rec(pull_vals)
            if not existing_pull:
                self.env['procurement.rule'].create(pull_vals)
            else:
                existing_pull.write({'active': self.manufacture_steps != 'manu_only'})
        return manufacture_route.id

    def create_or_update_manufacture_route(self):
        for warehouse in self:
            warehouse._create_or_update_locations()
            warehouse._create_or_update_manufacturing_picking_types()
            warehouse._create_or_update_manufacturing_route()
            manu_mto_pull_id = warehouse._create_or_update_manufacturing_mto_pull()
            manu_pull_id = warehouse._create_or_update_manufacture_pull()
            multistep_manu_route_id = warehouse._create_or_update_additional_step_routes()
            warehouse.write({'manu_mto_pull_id': manu_mto_pull_id,
                             'manufacture_pull_id': manu_pull_id,
                             'multistep_manu_route_id': multistep_manu_route_id,
                             'route_ids': [(4, multistep_manu_route_id)]})
        return True

    @api.multi
    def create_routes(self):
        res = super(StockWarehouse, self).create_routes()
        self.ensure_one()
        routes_data = self.get_routes_dict()
        manufacture_pull = self._create_or_update_manufacture_pull(routes_data)
        res['manufacture_pull_id'] = manufacture_pull.id
        return res

    @api.multi
    def write(self, vals):
        if 'manufacture_to_resupply' in vals:
            if vals.get("manufacture_to_resupply"):
                for warehouse in self.filtered(lambda warehouse: not warehouse.manufacture_pull_id):
                    manufacture_pull = warehouse._create_or_update_manufacture_pull(self.get_routes_dict())
                    vals['manufacture_pull_id'] = manufacture_pull.id
                for warehouse in self:
                    if not warehouse.manu_type_id:
                        warehouse._create_manufacturing_picking_type()
                    warehouse.manu_type_id.active = True
            else:
                for warehouse in self:
                    if warehouse.manu_type_id:
                        warehouse.manu_type_id.active = False
                self.mapped('manufacture_pull_id').unlink()
        return super(StockWarehouse, self).write(vals)

    @api.multi
    def _get_all_routes(self):
        routes = super(StockWarehouse, self).get_all_routes_for_wh()
        routes |= self.filtered(lambda self: self.manufacture_to_resupply and self.manufacture_pull_id and self.manufacture_pull_id.route_id).mapped('manufacture_pull_id').mapped('route_id')
        return routes

    @api.multi
    def _update_name_and_code(self, name=False, code=False):
        res = super(StockWarehouse, self)._update_name_and_code(name, code)
        # change the manufacture procurement rule name
        for warehouse in self:
            if warehouse.manufacture_pull_id and name:
                warehouse.manufacture_pull_id.write({'name': warehouse.manufacture_pull_id.name.replace(warehouse.name, name, 1)})
        return res
