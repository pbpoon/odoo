# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.Model):
    _name = 'wysiwyg.editor'

    name = fields.Char()
    html_field = fields.Html(string="HTML Editor")
