from odoo import models, fields, api

class CustomBillLine(models.Model):
    _name = 'custom.bill.line'
    _description = 'Jewelry Bill Line Item'

    # --- The Invisible Link Back to the Header ---
    bill_id = fields.Many2one('custom.bill', string='Bill Reference',invisible=True,readonly=True,ondelete='cascade')

    # --- Line Item Fields ---
    name = fields.Char(string='Name', required=True)
    weight = fields.Float(string='Weight', digits=(16, 4))
    less = fields.Float(string='Less', digits=(16, 4))
    melting = fields.Float(string='Melting')
    touch = fields.Float(string='Touch')
    pure = fields.Float(
        string="Pure",
        compute="_compute_pure",
        store=True,
        digits=(16, 4)
    )
    charges = fields.Float(string='Charges')
    net_weight = fields.Float(
        compute="_compute_net_weight",
        store=True,
        digits=(16, 4)
    )

    @api.depends('weight', 'less')
    def _compute_net_weight(self):
        for line in self:
            line.net_weight = line.weight - line.less

    @api.depends('weight', 'less', 'touch')
    def _compute_pure(self):
        for line in self:
            net_weight = line.weight - line.less
            line.pure = net_weight * (line.touch / 100.0)
    