from odoo import models, fields, api

# 1. NEW MODEL: This creates a separate table to hold unlimited images
class CustomJewelryOrderImage(models.Model):
    _name = 'custom.jewelry.order.image'
    _description = 'Order Reference Image'

    order_id = fields.Many2one('custom.jewelry.order', string='Order Reference', ondelete='cascade')
    name = fields.Char(string='Title', required=True, default='Reference Photo')
    image = fields.Image(string='Image', required=True, max_width=1024, max_height=1024)
    notes = fields.Text(string='Specific Notes (e.g., "Make this part thicker")')


# 2. MAIN MODEL: Your existing order model, updated to link to the images
class CustomJewelryOrder(models.Model):
    _name = 'custom.jewelry.order'
    _description = 'Custom Jewelry Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    date_order = fields.Date(string='Order Date', default=fields.Date.context_today)
    expected_date = fields.Date(string='Expected Delivery')
    
    item_type = fields.Selection([
        ('ring', 'Ring'),
        ('necklace', 'Necklace'),
        ('bangle', 'Bangle/Bracelet'),
        ('repair', 'Repair/Polish')
    ], string='Item Type', required=True)
    
    karat_purity = fields.Selection([
        ('18k', '18K'),
        ('22k', '22K'),
        ('24k', '24K')
    ], string='Gold Purity')
    
    description = fields.Text(string='Design Notes / Description')
    
    # CHANGED: Replaced the single image with a link to our new image table
    reference_image_ids = fields.One2many('custom.jewelry.order.image', 'order_id', string='Reference Gallery')
    
    estimated_weight = fields.Float(string='Estimated Weight (g)', digits=(16, 3))
    advance_payment = fields.Float(string='Advance Deposit (₹)', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft / Estimation'),
        ('confirmed', 'Confirmed'),
        ('manufacturing', 'In Manufacturing'),
        ('ready', 'Ready for Pickup'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                last_order = self.search([], order='id desc', limit=1)
                next_num = int(last_order.name.split('-')[1]) + 1 if last_order and '-' in last_order.name else 1
                vals['name'] = f"ORD-{next_num:04d}"
        return super().create(vals_list)