from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError
from urllib.parse import quote

class JewelryPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        if 'jewelry_count' in counters:
            values['jewelry_count'] = request.env['custom.jewelry.order'].search_count([('partner_id', '=', partner.id)])
        return values

    @http.route(['/my/jewelry_orders'], type='http', auth="user", website=True)
    def portal_my_jewelry_orders(self, **kw):
        partner = request.env.user.partner_id
        orders = request.env['custom.jewelry.order'].search([('partner_id', '=', partner.id)])
        values = {
            'orders': orders,
            'page_name': 'jewelry_order',
        }
        return request.render("custom_jewelry_order.portal_my_jewelry_orders", values)

    # CHANGED: The route now only asks for a string (the token), no ID!
    @http.route(['/my/secure_order/<string:access_token>'], type='http', auth="public", website=True)
    def portal_my_jewelry_order_secure(self, access_token, **kw):
        order_sudo = request.env['custom.jewelry.order'].sudo().search([('access_token', '=', access_token)], limit=1)
        
        if not order_sudo:
            return request.not_found()

        # FETCH THE COLLECTION ASSIGNED TO THE PORTAL
        # We ask Odoo: "Find the 1 active collection where display_location is 'portal'"
        portal_collection = request.env['jewelry.collection'].sudo().search([
            ('display_location', '=', 'portal'), 
            ('active', '=', True)
        ], limit=1)
        
        # Extract the designs from that collection (if it exists)
        showcase_designs = portal_collection.design_ids if portal_collection else []

        values = {
            'order': order_sudo,
            'page_name': 'jewelry_order',
            'token': access_token, 
            'showcase_designs': showcase_designs, # Pass the designs to the website
        }
        # --- DIAGNOSTIC TRAP ---
        print(f"\n========== SHOWCASE DEBUG ==========")
        print(f"Found Collection: {portal_collection.name if portal_collection else 'NONE FOUND!'}")
        print(f"Number of Designs: {len(showcase_designs) if showcase_designs else 0}")
        print(f"====================================\n")
        return request.render("custom_jewelry_order.portal_jewelry_order_detail", values)

    @http.route('/jewelry/whatsapp_redirect', type='http', auth='user')
    def jewelry_whatsapp_redirect(self, phone=None, text='', **kw):
        # FIX: Re-encode the decoded text so it is safe to put inside an HTTP redirect header
        safe_text = quote(text)
        
        # Build the native iOS app URL using the safe text
        if phone:
            whatsapp_url = f"whatsapp://send?phone={phone}&text={safe_text}"
        else:
            whatsapp_url = f"whatsapp://send?text={safe_text}"
        
        # Send a 302 Redirect header directly to the browser
        return request.redirect(whatsapp_url, local=False)