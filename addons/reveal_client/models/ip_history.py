import odoo
from odoo import api, fields, models


class IPHistory(models.TransientModel):
    _name = 'reveal.ip.history'
    _description = 'IP History'

    ip = fields.Char(string='IP Address', required=True)
    visittimes_ids = fields.One2many('reveal.ip.visittime', 'ip_id', string='Visit Times')

    def create(self, vals):
        temp = self.search([['ip','=',vals['ip']]])
        
        new = False
        if not temp:
            temp = super(IPHistory, self).create(vals)
            new = True

        temp.write({
            'visittimes_ids': [(0, 0, {})]
        })
        return new

class VisitTime(models.TransientModel):
    _name = 'reveal.ip.visittime'
    _description = 'IP History'

    ip_id = fields.Many2one('reveal.ip.history', string="IP Address")
