from odoo import http
from odoo.http import request

class JewelryCatalog(http.Controller):
    @http.route(['/catalog'], type='http', auth="public", website=True)
    def show_catalog(self, search='', size_id='', tag_id='', min_weight='', max_weight='', **kwargs):
        domain = []

        # 1. Text search
        if search:
            domain += ['|', ('name', 'ilike', search), ('barcode', 'ilike', search)]

        # 2. Size & Tag filters
        if size_id:
            domain += [('size', '=', int(size_id))]
        if tag_id:
            domain += [('design_tag_ids', 'in', [int(tag_id)])]

        # 3. NEW: Weight Range Filters (using Net Weight)
        try:
            if min_weight:
                domain += [('weight', '>=', float(min_weight))]
            if max_weight:
                domain += [('weight', '<=', float(max_weight))]
        except ValueError:
            # This safely ignores the filter if a user types letters into the URL by accident
            pass 

        # 4. Fetch Data
        items = request.env['jewelry.barcode.item'].sudo().search(domain)
        sizes = request.env['jewelry.size'].sudo().search([])
        tags = request.env['jewelry.design.tag'].sudo().search([])

        # 5. Send to template
        return request.render('custom_jewelery_catalog.jewelry_public_catalog', {
            'items': items,
            'sizes': sizes,
            'tags': tags,
            'search': search,
            'selected_size': int(size_id) if size_id else 0,
            'selected_tag': int(tag_id) if tag_id else 0,
            'min_weight': min_weight,
            'max_weight': max_weight,
        })