from odoo import models, fields, api

class CustomJewelryOrderItemType(models.Model):
    _name = 'custom.jewelry.item.type'
    _description = 'Custom Jewelry Item Type'
    _order = 'name'

    name = fields.Char(string='Item Type', required=True)

class CustomJewelryOrderKarat(models.Model):
    _name = 'custom.jewelry.karat'
    _description = 'Custom Jewelry Karat'
    _order = 'name'

    name = fields.Char(string='Karat', required=True)

class CustomJewelryOrderSeal(models.Model):
    _name = 'custom.jewelry.seal'
    _description = 'Custom Jewelry Seal'
    _order = 'name'

    name = fields.Char(string='Seal', required=True)

class CustomJewelryOrder(models.Model):
    _name = 'custom.jewelry.order'
    _description = 'Custom Jewelry Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    date_order = fields.Date(string='Order Date', default=fields.Date.context_today)
    expected_date = fields.Date(string='Expected Delivery', tracking=True)
    
    item_type = fields.Many2one('custom.jewelry.item.type', string='Item Type', required=True)
    karat_purity = fields.Many2one('custom.jewelry.karat', string='Karat/Purity', required=True)
    seal = fields.Many2one('custom.jewelry.seal', string='Seal', required=True)
    
    weight = fields.Float(string='Weight per Piece (g)', required=True, tracking=True)
    pieces = fields.Integer(string='Number of Pieces', required=True, default=1)
    total_wt = fields.Float(string='Total Weight (g)', compute='_compute_total_weight', store=True, readonly=True)
    
    description = fields.Text(string='Design Notes / Description', tracking=True)
    reference_image_ids = fields.Many2many(
        'ir.attachment', 
        string='Reference Gallery'
    )
    
    state = fields.Selection([
        ('draft', 'Draft / Estimation'),
        ('confirmed', 'Confirmed'),
        ('manufacturing', 'In Manufacturing'),
        ('ready', 'Ready for Pickup'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', readonly=False, tracking=True)

    @api.depends('weight', 'pieces')
    def _compute_total_weight(self):
        for order in self:
            order.total_wt = order.weight * order.pieces

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                last_order = self.search([], order='id desc', limit=1)
                next_num = int(last_order.name.split('-')[1]) + 1 if last_order and '-' in last_order.name else 1
                if next_num > 50:
                    next_num = 1  # Reset to 1 if it exceeds 50
                vals['name'] = f"ORD-{next_num:04d}"
        return super().create(vals_list)