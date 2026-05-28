from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError

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

    @http.route(['/my/jewelry_order/<int:order_id>'], type='http', auth="public", website=True)
    def portal_my_jewelry_order_detail(self, order_id, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access('custom.jewelry.order', order_id, access_token)
        except (AccessError, MissingError):
            return request.not_found()
        except Exception as e:
            return request.not_found()

        values = {
            'order': order_sudo,
            'page_name': 'jewelry_order',
            'token': access_token, 
        }
        return request.render("custom_jewelry_order.portal_jewelry_order_detail", values)