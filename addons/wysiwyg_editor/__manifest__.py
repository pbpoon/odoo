# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'WYSIWYG Editor',
    'category': 'Website',
    'summary': 'Simple WYSIWYG Editor',
    'website': 'https://www.odoo.com',
    'version': '1.0',
    'description': """
Simple WYSIWYG Edito
========================

        """,
    'depends': ['web'],
    'data': [
        'views/wysiwyg_views.xml',
        'views/wysiwyg_template_views.xml'
    ],
    'installable': True,
}
