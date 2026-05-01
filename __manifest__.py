{
    'name': 'Custom Billing Assessment',
    'version': '19.0.1.1.0',
    'summary': 'Assessment billing with internal and external pricing tiers',
    'category': 'Accounting',
    'author': 'Custom Development',
    'depends': [
        'base',
        'sale_management',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'data/assessment_product.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
