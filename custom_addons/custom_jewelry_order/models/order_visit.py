from odoo import models, fields


class JewelryOrderVisit(models.Model):
    _name = 'jewelry.order.visit'
    _description = 'Portal Visit Log'
    _order = 'visit_date desc'

    order_id = fields.Many2one('custom.jewelry.order', string='Order', ondelete='cascade', index=True, required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', related='order_id.partner_id', store=True, index=True)
    manufacturer_id = fields.Many2one('custom.jewelry.manufacturer', string='Manufacturer', related='order_id.manufacturer_id', store=True)
    visit_date = fields.Datetime(string='Visit Time', default=fields.Datetime.now, index=True)
    ip_address = fields.Char(string='IP Address')
