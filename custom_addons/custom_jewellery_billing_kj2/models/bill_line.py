from odoo import models, fields, api

class CustomBillLine(models.Model):
    _name = 'custom.bill2.line'
    _description = 'Jewelry Bill Line Item'

    # --- The Invisible Link Back to the Header ---
    bill_id = fields.Many2one('custom.bill2', string='Bill Reference',readonly=True,ondelete='cascade')

    # --- Line Item Fields ---
    name = fields.Char(string='Name', required=True)
    weight = fields.Float(string='Weight', digits=(16, 4))
    less = fields.Float(string='Less', digits=(16, 4))
    melting = fields.Float(string='Melting', digits=(16, 2))
    touch = fields.Float(string='Touch', digits=(16, 2))
    VAT = fields.Float(string='VAT', digits=(16, 2))
    type = fields.Selection(
        string='Type',
        selection=[('22K', '22K'), ('18K', '18K')],
        required=True
    )
    total_wt = fields.Float(
        string="Total Wt.",
        compute="_compute_total_wt",
        store=True,
        digits=(16, 4)
    )
    pure = fields.Float(string='Pure', compute="_compute_pure", store=True, digits=(16, 4))
    charges = fields.Float(string='Charges')
    net_weight = fields.Float(
        compute="_compute_net_weight",
        store=True,
        digits=(16, 4)
    )

    cash = fields.Float(string='Cash', compute="_compute_cash", store=True, digits=(16, 2))

    @api.onchange('type')
    def _onchange_melting(self):
        for line in self:
            if line.type == '22K':
                line.melting = 92.0
            elif line.type == '18K':
                line.melting = 76.0

    @api.onchange('VAT', 'bill_id.karat_22', 'bill_id.karat_18', 'bill_id.karat_24', 'type')
    def _onchange_VAT(self):
        for line in self:
            karat_24 = line.bill_id.karat_24
            if not karat_24:
                continue
            if line.type == '22K' and line.bill_id.karat_22:
                computed = (line.VAT + 100) * line.bill_id.karat_22 / karat_24
                if abs(computed - line.touch) > 0.005:
                    line.touch = computed
            elif line.type == '18K' and line.bill_id.karat_18:
                computed = (line.VAT + 100) * line.bill_id.karat_18 / karat_24
                if abs(computed - line.touch) > 0.005:
                    line.touch = computed

    @api.onchange('touch', 'bill_id.karat_22', 'bill_id.karat_18', 'bill_id.karat_24', 'type')
    def _onchange_touch(self):
        for line in self:
            karat_24 = line.bill_id.karat_24
            if not karat_24:
                continue
            if line.type == '22K' and line.bill_id.karat_22:
                line.VAT = (line.touch * karat_24 / line.bill_id.karat_22) - 100
            elif line.type == '18K' and line.bill_id.karat_18:
                line.VAT = (line.touch * karat_24 / line.bill_id.karat_18) - 100

    @api.depends('weight', 'less')
    def _compute_net_weight(self):
        for line in self:
            line.net_weight = line.weight - line.less

    @api.depends('weight', 'less', 'VAT')
    def _compute_total_wt(self):
        for line in self:
            net_weight = line.weight - line.less
            line.total_wt = net_weight * ((line.VAT / 100.0) + 1)
    
    @api.depends('net_weight', 'touch')
    def _compute_pure(self):
        for line in self:
            if line.touch > 0:
                line.pure = line.net_weight * (line.touch / 100.0)
            else:
                line.pure = 0.0

    @api.depends('total_wt', 'charges', 'type', 'bill_id.karat_22', 'bill_id.karat_18')
    def _compute_cash(self):
        for line in self:
            if line.type == '22K':
                line.cash = line.total_wt * line.bill_id.karat_22 + line.charges
            elif line.type == '18K':
                line.cash = line.total_wt * line.bill_id.karat_18 + line.charges
    