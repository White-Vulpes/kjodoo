{
    'name': 'Jewelry Public Catalog',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Public website catalog for jewelry inventory',
    'description': """
        Creates a public-facing website catalog for jewelry items.
        Safely hides manufacturer codes, deductions, and making charges.
    """,
    'depends': ['website', 'custom_stock_barcode'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/catalog_share_views.xml',
        'views/catalog_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_jewelery_catalog/static/src/js/select_create_kanban_patch.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}