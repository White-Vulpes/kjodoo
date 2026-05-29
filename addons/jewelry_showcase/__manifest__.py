{
    'name': 'Jewelry Showcase & Collections',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Manage exclusive jewelry collections and showcase them across the site.',
    'depends': ['base', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/showcase_views.xml',
    ],
    'installable': True,
    'application': True, # This makes it show up as a main App in the dashboard!
}