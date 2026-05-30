from odoo import models, fields

class JewelryCollection(models.Model):
    _name = 'jewelry.collection'
    _description = 'Jewelry Collection'

    name = fields.Char(string='Collection Name', required=True)
    active = fields.Boolean(default=True)
    
    display_location = fields.Selection([
        ('portal', 'Customer Order Portal'),
        ('home', 'Homepage'),
        ('none', 'Not Currently Displayed')
    ], string='Display Location', default='none')
    
    # CHANGED: We now link directly to Odoo's core attachment system for bulk uploads
    image_ids = fields.Many2many('ir.attachment', string='Collection Images')