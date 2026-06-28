from odoo import models, fields


class JewelryCarouselInteraction(models.Model):
    _name = 'jewelry.carousel.interaction'
    _description = 'Design Showcase Carousel Interaction'
    _order = 'interaction_date desc'

    order_id = fields.Many2one('custom.jewelry.order', string='Order', ondelete='cascade', index=True, required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', related='order_id.partner_id', store=True, index=True)
    collection_id = fields.Many2one('jewelry.collection', string='Collection', ondelete='cascade', index=True)
    slide_index = fields.Integer(string='Slide Position')
    interaction_date = fields.Datetime(string='Viewed At', default=fields.Datetime.now, index=True)
    ip_address = fields.Char(string='IP Address')
