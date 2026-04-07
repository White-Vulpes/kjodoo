from odoo import models, fields, api

class GramRecord(models.Model):
    _name = 'gram.record'
    _description = 'Gram Record Management'

    name = fields.Char(string='Reference', required=True, default='New')
    
    grams = fields.Float(string='Grams', digits=(16, 3))
    rate = fields.Integer(string='Rate')
    amount = fields.Integer(string='Amount')
    
    status = fields.Selection([
        ('accepted', 'Accepted'),
        ('received', 'Received'),
        ('bill_generated', 'Bill Generated'),
        ('delivered', 'Delivered')
    ], string='Status', default='accepted', tracking=True)

    # Calculate Amount when Grams or Rate changes
    @api.onchange('grams', 'rate')
    def _onchange_grams_rate(self):
        for record in self:
            if record.grams and record.rate:
                record.amount = record.grams * record.rate

    # Calculate Grams when Amount changes (assuming Rate is already set)
    @api.onchange('amount')
    def _onchange_amount(self):
        for record in self:
            if record.amount and record.rate and record.rate > 0:
                record.grams = record.amount / record.rate