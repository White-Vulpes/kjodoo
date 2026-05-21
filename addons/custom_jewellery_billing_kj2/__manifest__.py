{
    'name': 'Custom Jewelry Billing KJ2',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Custom tabular billing engine with 1-to-25 looping serial numbers.',
    'author': 'White Vulpes',
    
    # We only depend on the 'base' Odoo engine. No Enterprise traps here.
    'depends': ['base', 'mail'],  # 'mail' is for chatter support
    
    # The order here is strictly important: Security MUST load before Views.
    'data': [
        'security/ir.model.access.csv',
        'views/bill_view.xml',
        'views/bill_report.xml',
    ],
    
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}