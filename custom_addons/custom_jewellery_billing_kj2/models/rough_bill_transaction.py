from odoo import models, fields, api
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)

class RoughBillTransaction(models.Model):
    _name = 'custom.rough.bill2.transaction'
    _description = 'Rough Bill Transaction Ledger'
    _order = 'date asc, id asc'

    bill_id = fields.Many2one('custom.rough.bill2', string='Rough Bill', required=True, ondelete='cascade')
    date = fields.Date(string='Date', default=fields.Date.context_today, readonly=True, required=True)

    ttype = fields.Selection([
        ('metal_recv', 'Metal Received'),
        ('metal_pay', 'Metal Payment'),
        ('cash_recv', 'Cash Received'),
        ('cash_pay', 'Cash Payment'),
        ('rate_cut', 'Rate Cut'),
        ['old_item', 'Old Item'],
        ['return_item', 'Return Item']
    ], string='Transaction Type', required=True)

    gross_weight = fields.Float(string='Gross Weight', digits=(16, 4))
    less = fields.Float(string='Less Weight', digits=(16, 4))
    net_weight = fields.Float(string='Net Weight', digits=(16, 4), compute='_compute_net_weight', store=True, readonly=False)
    purity = fields.Float(string='Purity (%)', digits=(16, 2))
    pure_weight = fields.Float(string='Pure Weight', digits=(16, 4), compute='_compute_pure_weight', store=True, readonly=False)
    rate = fields.Float(string='Rate', digits=(16, 2))
    amount = fields.Float(string='Amount (Cash)', digits=(16, 2), compute='_compute_amount', store=True, readonly=False)

    @api.depends('ttype', 'net_weight', 'purity')
    def _compute_pure_weight(self):
        for rec in self:
            if rec.ttype in ['metal_recv', 'metal_pay', 'old_item', 'return_item']:
                rec.pure_weight = float_round(rec.net_weight * (rec.purity / 100.0), precision_digits=4)

    @api.depends('ttype', 'pure_weight', 'rate')
    def _compute_amount(self):
        for rec in self:
            if rec.ttype == 'rate_cut' and rec.rate:
                rec.amount = float_round(rec.pure_weight * rec.rate, precision_digits=2)
            elif rec.ttype == 'old_item':
                rec.amount = float_round(rec.pure_weight * rec.rate, precision_digits=2)

    @api.onchange('ttype')
    def _onchange_ttype_rate_cut(self):
        for rec in self:
            if rec.ttype == 'rate_cut' and rec.pure_weight == 0:
                if rec.bill_id and rec.bill_id.balance_pure != 0:
                    rec.pure_weight = rec.bill_id.balance_pure

    @api.onchange('pure_weight', 'rate', 'ttype')
    def _onchange_weight_and_rate(self):
        for rec in self:
            if rec.ttype == 'rate_cut':
                if rec.pure_weight > 0 and rec.rate > 0:
                    rec.amount = float_round(rec.pure_weight * rec.rate, precision_digits=2)

    @api.onchange('amount', 'ttype')
    def _onchange_amount(self):
        for rec in self:
            if rec.ttype == 'rate_cut' and rec.amount > 0:
                if rec.pure_weight > 0:
                    rec.rate = float_round(rec.amount / rec.pure_weight, precision_digits=2)
                elif rec.rate > 0:
                    rec.pure_weight = float_round(rec.amount / rec.rate, precision_digits=4)

    @api.depends('gross_weight', 'less')
    def _compute_net_weight(self):
        for rec in self:
            if rec.ttype in ['metal_recv', 'metal_pay', 'old_item', 'return_item']:
                rec.net_weight = float_round(rec.gross_weight - rec.less, precision_digits=4)
