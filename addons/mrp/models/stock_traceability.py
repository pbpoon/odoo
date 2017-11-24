from odoo import models, api

class MrpStockReport(models.TransientModel):
    _inherit = 'stock.traceability.report'

    @api.model
    def get_links(self, move_line):
        res_model, res_id, ref = super(MrpStockReport, self).get_links(move_line)
        if move_line.production_id:
            res_model = 'mrp.production'
            res_id = move_line.production_id.id
            ref = move_line.production_id.name
        if move_line.move_id.unbuild_id:
            res_model = 'mrp.unbuild'
            res_id = move_line.move_id.unbuild_id.id
            ref = move_line.move_id.unbuild_id.name
        if move_line.move_id.consume_unbuild_id:
            res_model = 'mrp.unbuild'
            res_id = move_line.move_id.consume_unbuild_id.id
            ref = move_line.move_id.consume_unbuild_id.name
        return res_model, res_id, ref

    @api.model
    def get_linked_move_lines(self, move_line):
        move_lines, is_used = super(MrpStockReport, self).get_linked_move_lines(move_line)
        # return produced lines of unbuild order
        produced_lined = move_line.move_id.consume_unbuild_id and move_line.produce_line_ids
        # return consumed lines of production order
        consumed_lines = move_line.move_id.production_id and move_line.consume_line_ids
        # return consumed lines  if materials used in unbuild order
        is_consumed = move_line.move_id.unbuild_id and move_line.consume_line_ids
        # return produced lines if materials used in production order
        is_produced = move_line.move_id.raw_material_production_id and move_line.produce_line_ids
        if not move_lines:
            move_lines = produced_lined or consumed_lines
        if not is_used:
            is_used = is_consumed or is_produced
        return move_lines, is_used
