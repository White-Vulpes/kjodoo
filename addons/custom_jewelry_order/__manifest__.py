{
    'name': 'Jewelry Orders',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Manage custom jewelry manufacturing and repair orders',
    'depends': ['base', 'contacts'], # Add 'sale' here if you want it linked to standard quotations
    'data': [
        'security/ir.model.access.csv',
        'views/order_views.xml',
    ],
    'installable': True,
    'application': True,
}