{
    'name': 'RTGS Entries',
    'version': '1.0',
    'category': 'Operations',
    'summary': 'Manage RTGS entries with a Kanban workflow',
    'description': """
        A custom module to calculate amounts and grams dynamically 
        with a status bar and Kanban view.
    """,
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/gram_record_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            'rtgs_entries/static/src/css/kanban_custom.css',
        ],
    },
}