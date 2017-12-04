# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import controllers

from odoo import api, SUPERUSER_ID


def _auto_create_journal(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('payment.payment_acquirer_payu').try_loading_for_acquirer()
