{
    'name': "Odoo Reveal",
    'category': 'Tools',
    'depends': ['iap','crm','website'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/crm_view.xml',
        'data/acquisition_rule_data.xml'
    ],
}
