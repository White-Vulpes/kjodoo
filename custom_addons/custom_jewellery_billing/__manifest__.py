{
    'name': 'Custom Jewelry Billing',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Custom tabular billing engine with 1-to-25 looping serial numbers.',
    'description': """
        A lightweight, fast, custom billing module designed for high-precision
        calculations (3-decimal weight, less, melting, pure, charges) without 
        relying on the heavy Odoo Enterprise accounting stack.
    """,
    'author': 'Your Name/Company',
    
    # Base engine plus the barcode inventory module: bills are raised by
    # scanning tags, and closing an approval memo bills the kept pieces.
    'depends': ['base', 'custom_stock_barcode'],

    # The order here is strictly important: Security MUST load before Views.
    'data': [
        'security/ir.model.access.csv',
        'views/bill_view.xml',
        'views/approval_bill_views.xml',
        'views/bill_report.xml',
    ],
    
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}