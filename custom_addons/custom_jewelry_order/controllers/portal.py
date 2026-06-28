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
    
    @http.route(['/my/secure_order/<string:access_token>'], type='http', auth="public", website=True)
    def portal_my_jewelry_order_secure(self, access_token, **kw):
        order_sudo = request.env['custom.jewelry.order'].sudo().search([('access_token', '=', access_token)], limit=1)
        
        if not order_sudo:
            return request.not_found()

        request.env['jewelry.order.visit'].sudo().create({
            'order_id': order_sudo.id,
            'ip_address': request.httprequest.remote_addr,
        })

        showcase_collections = request.env['jewelry.collection'].sudo().search([
            ('display_location', '=', 'portal'), 
            ('active', '=', True)
        ])

        values = {
            'order': order_sudo,
            'page_name': 'jewelry_order',
            'token': access_token, 
            'showcase_collections': showcase_collections, 
        }
        return request.render("custom_jewelry_order.portal_jewelry_order_detail", values)

    @http.route('/jewelry/track_carousel', type='jsonrpc', auth='public', methods=['POST'])
    def jewelry_track_carousel(self, collection_id=None, slide_index=0, order_token=None, **kw):
        if not order_token or not collection_id:
            return {'ok': False}
        order = request.env['custom.jewelry.order'].sudo().search(
            [('access_token', '=', order_token)], limit=1
        )
        if not order:
            return {'ok': False}
        request.env['jewelry.carousel.interaction'].sudo().create({
            'order_id': order.id,
            'collection_id': int(collection_id),
            'slide_index': int(slide_index),
            'ip_address': request.httprequest.remote_addr,
        })
        return {'ok': True}

    @http.route('/jewelry/whatsapp_redirect', type='http', auth='user')
    def jewelry_whatsapp_redirect(self, phone=None, text='', **kw):
        safe_text = quote(text)
        if phone:
            whatsapp_url = f"whatsapp://send?phone={phone}&text={safe_text}"
        else:
            whatsapp_url = f"whatsapp://send?text={safe_text}"
        return request.redirect(whatsapp_url, local=False)