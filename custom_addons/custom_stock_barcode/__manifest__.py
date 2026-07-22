{
    'name': 'Jewelry Barcode Inventory',
    'version': '19.0.1.2.0',
    'category': 'Inventory/Jewelry',
    'summary': 'Manage jewelry items using unique Barcode IDs',
    'description': """
        This module provides a comprehensive system to manage jewelry stock based on unique barcode tags.
        
        Key Features:
        - Unique Barcode identification enforcement
        - Gross and Net Weight calculations
        - Multi-line deductions (Less) for stones, wax, enamel, etc.
        - Multi-line charge tracking (Making, Hallmarking, etc.)
        - Many2many Design tags for fast filtering and searching
        - High-resolution image storage for designs
    """,
    'author': 'Aayush',
    'website': '',
    
    # Any module necessary for this one to work correctly.
    # If you are tying this into your existing billing menu, you should add your 
    # billing module's technical name here (e.g., 'custom_jewellery_billing') 
    # instead of just 'base' so the menus load in the correct order.
    'depends': ['base'],

    # Always load security rules FIRST, then views.
    'data': [
        'security/ir.model.access.csv',
        'data/stock_verification_sequence.xml',
        'data/approval_sequence.xml',
        'views/views.xml',
        'views/import_wizard_view.xml',
        'views/stock_verification_views.xml',
        'views/approval_views.xml',
        'reports/tag_report.xml',
        'reports/stock_verification_report.xml',
    ],

    # Images/Assets
    'assets': {
        'web.assets_backend': [
            # Add any custom CSS/JS for the backend here if needed in the future
        ],
    },

    'installable': True,
    'application': True, # Set to True so it shows up in the main Apps dashboard
    'license': 'LGPL-3',
}