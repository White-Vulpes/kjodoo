from odoo import http
from odoo.http import request

class JewelryCatalog(http.Controller):
    @http.route(['/catalog'], type='http', auth="public", website=True)
    def show_catalog(self, search='', size_id='', tag_id='', **kwargs):
        # 1. Base domain (starts empty to show all)
        domain = []

        # 2. Add text search (searches Name OR Barcode)
        if search:
            domain += ['|', ('name', 'ilike', search), ('barcode', 'ilike', search)]

        # 3. Add Size filter
        if size_id:
            domain += [('size', '=', int(size_id))]

        # 4. Add Tag/Design filter
        if tag_id:
            domain += [('design_tag_ids', 'in', [int(tag_id)])]

        # 5. Fetch the filtered items
        items = request.env['jewelry.barcode.item'].sudo().search(domain)

        # 6. Fetch all available Sizes and Tags to populate the dropdowns
        sizes = request.env['jewelry.size'].sudo().search([])
        tags = request.env['jewelry.design.tag'].sudo().search([])

        # 7. Send everything to the template
        return request.render('custom_jewelery_catalog.jewelry_public_catalog', {
            'items': items,
            'sizes': sizes,
            'tags': tags,
            'search': search,
            # We pass back the selected IDs so the dropdowns "remember" what the user picked
            'selected_size': int(size_id) if size_id else 0,
            'selected_tag': int(tag_id) if tag_id else 0,
        })