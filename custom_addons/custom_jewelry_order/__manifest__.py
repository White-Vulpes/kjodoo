{
    'name': 'Jewelry Orders',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Manage custom jewelry manufacturing and repair orders',
    'depends': ['base', 'contacts', 'portal', 'web', 'jewelry_showcase'], # Add 'sale' here if you want it linked to standard quotations
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/order_views.xml',
        'views/dashboard_views.xml',
        'views/analytics_dashboard.xml',
        'views/portal_templates.xml',
        'reports/order_report.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'custom_jewelry_order/static/src/js/carousel_tracker.js',
        ],
        'web.assets_backend': [
            'custom_jewelry_order/static/src/scss/analytics_dashboard.scss',
            'custom_jewelry_order/static/src/js/analytics_dashboard.js',
            'custom_jewelry_order/static/src/xml/analytics_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
}