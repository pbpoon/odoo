# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_es_nif = fields.Char(string="NIF", related='partner_id.l10n_es_nif')
