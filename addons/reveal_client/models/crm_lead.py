from odoo import fields, models


class Lead(models.Model):
    _inherit = 'crm.lead'

    reveal_ip = fields.Char(string='IP Address')
    reveal_rule_id = fields.Many2one('reveal.lead.rule', string='Reveal Rule ID')
