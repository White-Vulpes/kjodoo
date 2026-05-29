from odoo import models, fields, api
from urllib.parse import quote
from datetime import timedelta

class JewelrySize(models.Model):
    _name = 'jewelry.size'
    _description = 'Jewelry Size'
    name = fields.Char(string='Size', required=True)

class JewelryBroadness(models.Model):
    _name = 'jewelry.broadness'
    _description = 'Jewelry Broadness'
    name = fields.Char(string='Broadness', required=True)

class JewelryMelting(models.Model):
    _name = 'jewelry.melting'
    _description = 'Melting Standard'
    name = fields.Char(string='Melting', required=True)

class CustomJewelryOrderItemType(models.Model):
    _name = 'custom.jewelry.item.type'
    _description = 'Custom Jewelry Item Type'
    _order = 'name'

    name = fields.Char(string='Item Type', required=True)

class CustomJewelryOrderSeal(models.Model):
    _name = 'custom.jewelry.seal'
    _description = 'Custom Jewelry Seal'
    _order = 'name'

    name = fields.Char(string='Seal', required=True)

class CustomJewelryOrderManufacturer(models.Model):
    _name = 'custom.jewelry.manufacturer'
    _description = 'Custom Jewelry Manufacturer'
    _order = 'name'

    name = fields.Char(string='Manufacturer', required=True)

class CustomJewelryOrder(models.Model):
    _name = 'custom.jewelry.order'
    _description = 'Custom Jewelry Order'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    manufacturer_id = fields.Many2one('custom.jewelry.manufacturer', string='Manufacturer / Karigar', tracking=True)
    date_order = fields.Date(string='Order Date', default=fields.Date.context_today)
    expected_date = fields.Date(string='Expected Delivery', tracking=True)

    size_id = fields.Many2one('jewelry.size', string='Size / Length')
    broadness_id = fields.Many2one('jewelry.broadness', string='Broadness')
    melting_id = fields.Many2one('jewelry.melting', string='Melting')
    
    item_type = fields.Many2one('custom.jewelry.item.type', string='Item Type', required=True)
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
        ('cancelled', 'Cancelled'),
        ('draft', 'Draft / Estimation'),
        ('confirmed', 'Confirmed'),
        ('manufacturing', 'In Manufacturing'),
        ('ready', 'Ready for Pickup'),
        ('delivered', 'Delivered')
    ], string='Status', default='draft', readonly=False, tracking=True, group_expand='_read_group_state')

    # 1. The invisible field that holds the True/False calculation
    is_delivery_urgent = fields.Boolean(
        string='Is Delivery Urgent', 
        compute='_compute_delivery_urgent'
    )

    # 2. The brain that calculates the urgency
    @api.depends('expected_date', 'state')
    def _compute_delivery_urgent(self):
        # We define "urgent" as being 3 days or less from today
        today = fields.Date.context_today(self)
        urgent_date_threshold = today + timedelta(days=3)
        
        for order in self:
            # If there's no date, or the item is already ready/delivered/cancelled, it's NOT urgent
            if not order.expected_date or order.state in ('ready', 'delivered', 'cancelled'):
                order.is_delivery_urgent = False
            else:
                # If the expected date is less than or equal to our 3-day threshold (or in the past)
                if order.expected_date <= urgent_date_threshold:
                    order.is_delivery_urgent = True
                else:
                    order.is_delivery_urgent = False

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
    
    def action_print_order(self):
        self.ensure_one()
        
        # 1. Fetch the report action record directly
        report_action = self.env.ref('custom_jewelry_order.action_report_custom_jewelry_order')
        
        # 2. Return Odoo's native report engine action
        # This automatically handles the PDF generation and honors 'print_report_name'
        return report_action.report_action(self)
    
    @api.model
    def _read_group_state(self, *args, **kwargs):
        return [
            'draft', 
            'confirmed', 
            'manufacturing', 
            'ready', 
            'delivered', 
            'cancelled'
        ]
    
    def action_send_whatsapp(self):
        self.ensure_one()

        # 1. Generate the portal link and message
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_link = f"{base_url}{self.get_portal_url()}"
        state_label = dict(self._fields['state'].selection).get(self.state, self.state)

        message = (
            f"Hello {self.partner_id.name},\n\n"
            f"Your custom jewelry order {self.name} is currently in the '{state_label}' stage.\n\n"
            f"You can view your design specs, reference photos, and chat with us directly here:\n{portal_link}\n\n"
            f"Thank you for choosing us!"
        )
        encoded_message = quote(message)

        # 2. Smart Routing for iOS and Android
        # Check if the customer has a mobile number saved
        if self.partner_id.mobile:
            # Strip out any spaces or special characters from the phone number
            clean_phone = ''.join(filter(str.isdigit, self.partner_id.mobile))
            
            # Using the native scheme with the phone number opens the exact chat
            whatsapp_url = f"whatsapp://send?phone={clean_phone}&text={encoded_message}"
        else:
            # Using the native scheme without a phone number forces the contact picker to open reliably on iOS
            whatsapp_url = f"whatsapp://send?text={encoded_message}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': whatsapp_url,
            'target': 'new',
        }
    
    # Overrides the default Odoo portal URL generator
    def _compute_access_url(self):
        super(CustomJewelryOrder, self)._compute_access_url()
        for order in self:
            # 1. Force Odoo to generate a token if it doesn't have one yet
            if not order.access_token:
                order._portal_ensure_token()
            
            # 2. Build the new completely ID-less URL
            order.access_url = f'/my/secure_order/{order.access_token}'