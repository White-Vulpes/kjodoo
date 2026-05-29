from odoo import models, fields

class JewelryCollection(models.Model):
    _name = 'jewelry.collection'
    _description = 'Jewelry Collection'

    name = fields.Char(string='Collection Name', required=True)
    active = fields.Boolean(default=True)
    
    # This dictates where the collection is currently being advertised
    display_location = fields.Selection([
        ('portal', 'Customer Order Portal'),
        ('home', 'Homepage'),
        ('none', 'Not Currently Displayed')
    ], string='Display Location', default='none')
    
    # Links to the designs inside this collection
    design_ids = fields.One2many('jewelry.design', 'collection_id', string='Designs')

class JewelryDesign(models.Model):
    _name = 'jewelry.design'
    _description = 'Exclusive Design'
    _order = 'sequence, id'

    name = fields.Char(string='Design Name', required=True)
    image = fields.Image(string='Image', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    collection_id = fields.Many2one('jewelry.collection', string='Collection', ondelete='cascade')