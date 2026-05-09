from odoo import models, fields, api

class CustomBillLine(models.Model):
    _name = 'custom.bill2.line'
    _description = 'Jewelry Bill Line Item'

    # --- The Invisible Link Back to the Header ---
    bill_id = fields.Many2one('custom.bill2', string='Bill Reference',invisible=True,readonly=True,ondelete='cascade')

    # --- Line Item Fields ---
    name = fields.Char(string='Name', required=True)
    weight = fields.Float(string='Weight', digits=(16, 4))
    less = fields.Float(string='Less', digits=(16, 4))
    melting = fields.Float(string='Melting')
    VAT = fields.Float(string='VAT')
    total_wt = fields.Float(
        string="Total Wt.",
        compute="_compute_total_wt",
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

    @api.depends('weight', 'less', 'VAT')
    def _compute_total_wt(self):
        for line in self:
            net_weight = line.weight - line.less
            line.total_wt = net_weight * ((line.VAT / 100.0) + 1)
    