from odoo import models, fields, api
from odoo.tools.float_utils import float_round

class CustomBillTransaction(models.Model):
    _name = 'custom.bill.transaction'
    _description = 'Bill Transaction Ledger'
    _order = 'date asc, id asc'

    bill_id = fields.Many2one('custom.bill', string='Bill', required=True, ondelete='cascade')
    date = fields.Date(string='Date', default=fields.Date.context_today, readonly=True, required=True)
    
    ttype = fields.Selection([
        ('metal_recv', 'Metal Received'),
        ('metal_pay', 'Metal Payment'),
        ('cash_recv', 'Cash Received'),
        ('cash_pay', 'Cash Payment'),
        ('rate_cut', 'Rate Cut')
    ], string='Transaction Type', required=True)
    
    gross_weight = fields.Float(string='Gross Weight', digits=(16, 3))
    purity = fields.Float(string='Purity (%)', digits=(16, 2))
    
    # Used for Metal transactions AND the weight used in a Rate Cut
    pure_weight = fields.Float(string='Pure Weight', digits=(16, 3), compute='_compute_pure_weight', store=True, readonly=False)

    # --- Cash / Rate Fields ---
    rate = fields.Float(string='Rate', digits=(16, 2))
    amount = fields.Float(string='Amount (Cash)', digits=(16, 2), compute='_compute_amount', store=True, readonly=False)

    @api.depends('ttype', 'gross_weight', 'purity')
    def _compute_pure_weight(self):
        for rec in self:
            if rec.ttype in ['metal_recv', 'metal_pay']:
                # Convert Kacha to Pure
                rec.pure_weight = float_round(rec.gross_weight * (rec.purity / 100.0), precision_digits=3)

    @api.depends('ttype', 'pure_weight', 'rate')
    def _compute_amount(self):
        for rec in self:
            if rec.ttype == 'rate_cut' and rec.rate:
                # Convert Pure to Cash
                rec.amount = float_round(rec.pure_weight * rec.rate, precision_digits=2)
    
    @api.onchange('ttype')
    def _onchange_ttype_rate_cut(self):
        for rec in self:
            # When the user selects 'Rate Cut' and the weight is currently 0
            if rec.ttype == 'rate_cut' and rec.pure_weight == 0:
                
                # Access the parent bill's live balance_pure
                if rec.bill_id and rec.bill_id.balance_pure > 0:
                    rec.pure_weight = rec.bill_id.balance_pure