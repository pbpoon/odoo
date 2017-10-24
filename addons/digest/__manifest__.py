# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'KPI Digests',
    'version': '1.0',
    'category': 'Mail',
    'description': """
Send KPI Digests periodically
=============================
* Send KPI digest emails periodically (daily, weekly, monthly, quarterly)
""",
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/digest_template_data.xml',
        'data/digest_data.xml',
        'data/ir_cron_data.xml',
        'views/digest_views.xml',
    ],
    'installable': True,
}
