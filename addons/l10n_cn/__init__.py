# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (C) 2007-2014 Jeff Wang(<http://jeff@osbzr.com>).

from odoo import api, SUPERUSER_ID


def _auto_install_l10n_cn(cr, registry):
    # Check the module, If we install l10n_cn then it should automatically install one of the COA for china l10n_cn + l10n_cn_small_business
    # If we install l10n_standard and not installed l10n_cn_small_business then it should install only l10n_cn + l10n_cn_standard not need to install l10n_cn_small_business
    env = api.Environment(cr, SUPERUSER_ID, {})
    module_to_install = env['ir.module.module'].search([('state', '=', 'to install'), ('name', 'in', ['l10n_cn_small_business', 'l10n_cn_standard'])])
    if not module_to_install:
        module = env['ir.module.module'].search([('name', '=', 'l10n_cn_small_business'), ('state', '=', 'uninstalled')])
        module.button_install()
