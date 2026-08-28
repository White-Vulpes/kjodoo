import uuid
from datetime import timedelta

from odoo import api, fields, models


class JewelryCatalogShare(models.Model):
    """A curated, time-limited public catalog link.

    Staff pick a handful of designs and hand the customer a URL
    (/catalog/share/<token>) that shows ONLY those designs and stops
    working once it expires (1 hour after creation by default). Each link
    is independent, so many customers can each get their own selection.
    """
    _name = 'jewelry.catalog.share'
    _description = 'Shared Jewelry Catalog Link'
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference', required=True,
        help="Internal label for this link, e.g. the customer's name. "
             "Not shown to the customer.")
    token = fields.Char(
        string='Token', required=True, index=True, copy=False, readonly=True,
        default=lambda self: uuid.uuid4().hex)
    item_ids = fields.Many2many(
        'jewelry.barcode.item', 'jewelry_catalog_share_item_rel',
        'share_id', 'item_id', string='Designs',
        help="Only these designs are shown on the shared link.")
    item_count = fields.Integer(
        string='Design Count', compute='_compute_item_count')
    customer_cart_item_ids = fields.Many2many(
        'jewelry.barcode.item', 'jewelry_catalog_share_cart_rel',
        'share_id', 'item_id', string='Customer Selection', readonly=True,
        help="Designs the customer picked on the shared link.")
    customer_cart_count = fields.Integer(
        string='Selected by Customer', compute='_compute_customer_cart_count')
    cart_updated_on = fields.Datetime(
        string='Selection Updated', readonly=True,
        help="When the customer last changed their selection.")
    valid_hours = fields.Float(
        string='Valid For (hours)', default=1.0, required=True,
        help="The link stops working this many hours after it is created.")
    expiry = fields.Datetime(
        string='Expires On', compute='_compute_expiry', store=True)
    is_expired = fields.Boolean(
        string='Expired', compute='_compute_is_expired',
        search='_search_is_expired')
    share_url = fields.Char(
        string='Share Link', compute='_compute_share_url')
    active = fields.Boolean(default=True)

    _token_uniq = models.Constraint('unique(token)',
        "The share token must be unique.")

    @api.depends('item_ids')
    def _compute_item_count(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)

    @api.depends('customer_cart_item_ids')
    def _compute_customer_cart_count(self):
        for rec in self:
            rec.customer_cart_count = len(rec.customer_cart_item_ids)

    def _record_customer_cart(self, barcodes):
        """Persist the customer's on-page selection so staff can see it.

        Only barcodes that belong to this link's curated designs are kept,
        so a tampered request can't attach arbitrary inventory.
        """
        self.ensure_one()
        barcodes = [b for b in (barcodes or []) if b]
        items = self.item_ids.filtered(lambda i: i.barcode in barcodes)
        self.write({
            'customer_cart_item_ids': [(6, 0, items.ids)],
            'cart_updated_on': fields.Datetime.now(),
        })
        return len(items)

    @api.depends('create_date', 'valid_hours')
    def _compute_expiry(self):
        for rec in self:
            if rec.create_date:
                rec.expiry = rec.create_date + timedelta(hours=rec.valid_hours or 0.0)
            else:
                rec.expiry = False

    @api.depends('expiry')
    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_expired = bool(rec.expiry and rec.expiry < now)

    def _search_is_expired(self, operator, value):
        if operator not in ('=', '!='):
            raise NotImplementedError(
                "Unsupported operator %s for is_expired" % operator)
        now = fields.Datetime.now()
        # Resolve the query down to "should we return expired records?".
        want_expired = (operator == '=') == bool(value)
        if want_expired:
            return [('expiry', '<', now)]
        return ['|', ('expiry', '=', False), ('expiry', '>=', now)]

    def _compute_share_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.share_url = f"{base_url}/catalog/share/{rec.token}" if rec.token else False

    def action_open_share_link(self):
        """Open the customer-facing link in a new browser tab."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f"/catalog/share/{self.token}",
            'target': 'new',
        }
