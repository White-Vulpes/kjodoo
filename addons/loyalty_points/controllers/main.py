# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
class HelloWorld(http.Controller):
   @http.route('/loyaltypoints', type='http', auth='public', website=True)
   def loyalty_points_page(self, **kwargs):
       """
       This controller handles the request for the /loyaltypoints page.
       It renders a QWeb template and passes a dynamic value.
       """
       user_name = request.env.user.name if request.env.user.id else 'Guest'

       return request.render('loyalty_points.loyalty_points_template', {
           'user_name': user_name,
       })
