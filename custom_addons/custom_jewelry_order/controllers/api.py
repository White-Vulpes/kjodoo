import hmac

from odoo import fields, http
from odoo.http import request

# System parameter that stores the secret expected in the X-API-Key header.
# It is auto-provisioned with a random value on module install/upgrade
# (see the post_init_hook in the module __init__) and can be rotated from
# Settings > Technical > System Parameters.
API_KEY_PARAM = 'custom_jewelry_order.api_key'

# States that count as "still open" (not yet handed to the customer, not dropped)
PENDING_STATES = ('draft', 'confirmed', 'manufacturing', 'ready')

# Urgency window mirrors CustomJewelryOrder._compute_delivery_urgent (3 days).
URGENT_WINDOW_DAYS = 3

# How many days back the daily-trend history covers.
HISTORY_WINDOW_DAYS = 30


class JewelryOrderApi(http.Controller):

    def _check_api_key(self):
        """Return None when the request carries a valid API key, otherwise a
        JSON error response ready to be returned to the caller."""
        expected = request.env['ir.config_parameter'].sudo().get_param(API_KEY_PARAM)
        if not expected:
            return request.make_json_response(
                {'error': 'API key not configured on the server.'}, status=503
            )
        provided = request.httprequest.headers.get('X-API-Key', '')
        # Constant-time comparison avoids leaking the key through timing.
        if not provided or not hmac.compare_digest(provided, expected):
            return request.make_json_response(
                {'error': 'Invalid or missing API key.'}, status=401
            )
        return None

    @http.route('/api/jewelry/order_stats', type='http', auth='public',
                methods=['GET'], csrf=False)
    def jewelry_order_stats(self, **kw):
        auth_error = self._check_api_key()
        if auth_error is not None:
            return auth_error

        Order = request.env['custom.jewelry.order'].sudo()
        today = fields.Date.context_today(Order)
        urgent_threshold = fields.Date.to_string(
            fields.Date.add(today, days=URGENT_WINDOW_DAYS)
        )
        today_str = fields.Date.to_string(today)

        # One grouped read gives us every per-state count in a single query.
        state_groups = Order.read_group([], ['state'], ['state'])
        by_state = {g['state']: g['state_count'] for g in state_groups if g['state']}

        pending = sum(by_state.get(s, 0) for s in PENDING_STATES)

        # "Urgent" and "overdue" depend on expected_date, so they need their
        # own domains (is_delivery_urgent is a non-stored computed field and
        # cannot be searched directly).
        open_states = ['ready', 'delivered', 'cancelled']
        urgent = Order.search_count([
            ('expected_date', '!=', False),
            ('expected_date', '<=', urgent_threshold),
            ('state', 'not in', open_states),
        ])
        overdue = Order.search_count([
            ('expected_date', '!=', False),
            ('expected_date', '<', today_str),
            ('state', 'not in', ['delivered', 'cancelled']),
        ])

        # Daily trend: how many orders were created on each of the last
        # HISTORY_WINDOW_DAYS days, zero-filled so callers get one entry per
        # day (oldest first) and can plot a continuous line.
        history_start = fields.Date.subtract(today, days=HISTORY_WINDOW_DAYS - 1)
        recent_orders = Order.search_read(
            [('date_order', '>=', fields.Date.to_string(history_start))],
            ['date_order'],
        )
        daily_counts = {}
        for rec in recent_orders:
            order_day = rec['date_order']
            if order_day:
                daily_counts[order_day] = daily_counts.get(order_day, 0) + 1
        history = [
            daily_counts.get(fields.Date.add(history_start, days=offset), 0)
            for offset in range(HISTORY_WINDOW_DAYS)
        ]

        data = {
            'total_orders': sum(by_state.values()),
            'pending_orders': pending,
            'delivered_orders': by_state.get('delivered', 0),
            'urgent_orders': urgent,
            'overdue_orders': overdue,
            'by_state': {
                'draft': by_state.get('draft', 0),
                'confirmed': by_state.get('confirmed', 0),
                'manufacturing': by_state.get('manufacturing', 0),
                'ready': by_state.get('ready', 0),
                'delivered': by_state.get('delivered', 0),
                'cancelled': by_state.get('cancelled', 0),
            },
            'history': history,
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
        }
        return request.make_json_response(data)
