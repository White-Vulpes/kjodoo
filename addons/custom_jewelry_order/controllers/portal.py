from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class JewelryPortal(CustomerPortal):

    # 1. Adds the counter to the main "My Account" page
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        if 'jewelry_count' in counters:
            values['jewelry_count'] = request.env['custom.jewelry.order'].search_count([('partner_id', '=', partner.id)])
        return values

    # 2. The URL for the List View
    @http.route(['/my/jewelry_orders'], type='http', auth="user", website=True)
    def portal_my_jewelry_orders(self, **kw):
        partner = request.env.user.partner_id
        orders = request.env['custom.jewelry.order'].search([('partner_id', '=', partner.id)])
        values = {
            'orders': orders,
            'page_name': 'jewelry_order',
        }
        return request.render("custom_jewelry_order.portal_my_jewelry_orders", values)

    # 3. The URL for the specific Order details
    # CHANGED: auth="public" allows non-logged-in users with the secret token
    @http.route(['/my/jewelry_order/<int:order_id>'], type='http', auth="public", website=True)
    def portal_my_jewelry_order_detail(self, order_id, access_token=None, **kw):
        try:
            # Odoo automatically checks if the access_token in the URL matches the database
            order_sudo = self._document_check_access('custom.jewelry.order', order_id, access_token)
        except:
            return request.redirect('/my')

        values = {
            'order': order_sudo,
            'page_name': 'jewelry_order',
            # We must pass the token to the webpage so the Chatter knows who is typing
            'token': access_token, 
        }
        return request.render("custom_jewelry_order.portal_jewelry_order_detail", values)