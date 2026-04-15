# -*- coding: utf-8 -*-
{
   'name': 'Loyalty Points',
   'version': '19.0.1.0.0',
   'summary': 'A module to create a custom web page in Odoo.',
   'author': 'Aayush Parmar',
   'website': 'https://www.aayushparmar.in',
   'category': 'Website',
   'depends': [
       'base','website',
   ],
   'data': [
       'views/templates.xml',
   ],
   'assets': {'web.assets_frontend': [
            'loyalty_points/static/src/css/templates.css',
        ],},
   'installable': True,
   'application': False,
   'auto_install': False,
}
