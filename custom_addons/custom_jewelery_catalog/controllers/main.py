from odoo import http
from odoo.http import request

class JewelryCatalog(http.Controller):
    @http.route(['/catalog'], type='http', auth="public", website=True)
    def show_catalog(self, search='', size_id='', min_weight='', max_weight='', **kwargs):
        domain = []

        # 1. Capture MULTIPLE tag IDs from the URL
        # request.httprequest.args.getlist safely grabs all 'tag_ids' passed in the URL
        tag_ids_str = request.httprequest.args.getlist('tag_ids')
        
        # Convert the string IDs to integers (ignoring any empty/invalid values)
        selected_tags = [int(t) for t in tag_ids_str if t.isdigit()]

        # 2. Text Search
        if search:
            domain += ['|', ('name', 'ilike', search), ('barcode', 'ilike', search)]

        # 3. Size Filter
        if size_id:
            domain += [('size', '=', int(size_id))]

        # 4. NEW: Multi-Tag Filter
        if selected_tags:
            # Using 'in' with a list will return items that have ANY of the selected tags
            domain += [('design_tag_ids', 'in', selected_tags)]

        # 5. Weight Range
        try:
            if min_weight:
                domain += [('net_weight', '>=', float(min_weight))]
            if max_weight:
                domain += [('net_weight', '<=', float(max_weight))]
        except ValueError:
            pass 

        # 6. Fetch Data
        items = request.env['jewelry.barcode.item'].sudo().search(domain)
        sizes = request.env['jewelry.size'].sudo().search([])
        tags = request.env['jewelry.design.tag'].sudo().search([])

        # 7. Send to template
        return request.render('custom_jewelery_catalog.jewelry_public_catalog', {
            'items': items,
            'sizes': sizes,
            'tags': tags,
            'search': search,
            'selected_size': int(size_id) if size_id else 0,
            'selected_tags': selected_tags,  # Pass the LIST of selected tags back to the UI
            'min_weight': min_weight,
            'max_weight': max_weight,
            'share_mode': False,
            'share_token': '',
        })

    @http.route(['/catalog/share/<string:token>'], type='http',
                auth="public", website=True, sitemap=False)
    def show_shared_catalog(self, token, **kwargs):
        """A curated, time-limited link: shows ONLY the designs staff picked
        for this token, and refuses the page once the link has expired."""
        share = request.env['jewelry.catalog.share'].sudo().search(
            [('token', '=', token)], limit=1)

        # Unknown token or past its expiry window -> generic closed page.
        if not share or share.is_expired:
            return request.render('custom_jewelery_catalog.jewelry_catalog_expired', {})

        # Only surface designs that are still in stock (0-piece tags are archived).
        items = share.item_ids.filtered(lambda i: i.active)

        return request.render('custom_jewelery_catalog.jewelry_public_catalog', {
            'items': items,
            'sizes': [],
            'tags': [],
            'search': '',
            'selected_size': 0,
            'selected_tags': [],
            'min_weight': '',
            'max_weight': '',
            'share_mode': True,
            'share_token': token,
        })

    @http.route(['/catalog/share/<string:token>/cart'], type='jsonrpc',
                auth="public", methods=['POST'])
    def save_shared_cart(self, token, barcodes=None, **kwargs):
        """Store the customer's live selection on the share record so staff
        can see what they picked, straight from Odoo."""
        share = request.env['jewelry.catalog.share'].sudo().search(
            [('token', '=', token)], limit=1)
        if not share or share.is_expired:
            return {'ok': False}
        count = share._record_customer_cart(barcodes)
        return {'ok': True, 'count': count}