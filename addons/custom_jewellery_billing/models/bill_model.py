from odoo import models, fields, api
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)

class CustomBill(models.Model):
    _name = 'custom.bill'
    _description = 'Jewelry Bill'
    # This tells Odoo to use our 'name' char field as the record label
    _rec_name = 'name' 
    _order = 'id desc'
    
    # This is the "Display Name" (e.g., "Bill #5")
    name = fields.Char(string='Bill Reference', required=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    
    bill_number = fields.Integer(string='Bill Number', copy=False, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)

    # --- The Relational Table ---
    item_ids = fields.One2many('custom.bill.line', 'bill_id', string='Bill Items')

    # --- The Totals ---
    total_weight = fields.Float(string='Total Weight', compute='_compute_totals', store=True, digits=(16, 4))
    total_pure = fields.Float(string='Total Pure', compute='_compute_totals', store=True, digits=(16, 4))
    total_net_weight = fields.Float(string='Total Net Weight', compute='_compute_totals', store=True, digits=(16, 4))
    total_charges = fields.Float(string='Total Charges', compute='_compute_totals', store=True)
    total_less = fields.Float(string='Total Less', compute='_compute_totals', store=True, digits=(16, 4))

    # Add the relational field
    transaction_ids = fields.One2many('custom.bill.transaction', 'bill_id', string='Transactions')

    # Add the live balance fields
    balance_pure = fields.Float(string='Remaining Pure', compute='_compute_balances', store=True, digits=(16, 3))
    balance_charges = fields.Float(string='Remaining Balance', compute='_compute_balances', store=True, digits=(16, 2))

    @api.depends(
        'total_pure', 'total_charges', 
        'transaction_ids.ttype', 'transaction_ids.pure_weight', 'transaction_ids.amount'
    )
    def _compute_balances(self):
        for bill in self:
            # Start with the totals from the items
            running_pure = bill.total_pure
            running_charges = bill.total_charges

            for txn in bill.transaction_ids:
                if txn.ttype == 'metal_recv':
                    running_pure -= txn.pure_weight
                elif txn.ttype == 'metal_pay':
                    running_pure += txn.pure_weight
                elif txn.ttype == 'cash_recv':
                    running_charges -= txn.amount
                elif txn.ttype == 'cash_pay':
                    running_charges += txn.amount
                elif txn.ttype == 'rate_cut':
                    running_pure -= txn.pure_weight
                    running_charges += txn.amount  # Adds the cash value of the cut metal

            bill.balance_pure = float_round(running_pure, precision_digits=3)
            bill.balance_charges = float_round(running_charges, precision_digits=2)

    @api.depends('item_ids.weight', 'item_ids.pure', 'item_ids.charges', 'item_ids.less', 'item_ids.net_weight')
    def _compute_totals(self):
        for bill in self:
            bill.total_weight = float_round(sum(line.weight for line in bill.item_ids), precision_digits=4)
            bill.total_pure = float_round(sum(line.pure for line in bill.item_ids), precision_digits=4)
            bill.total_less = float_round(sum(line.less for line in bill.item_ids), precision_digits=4)
            bill.total_net_weight = float_round(sum(line.net_weight for line in bill.item_ids), precision_digits=4)
            base_charges = float_round(sum(line.charges for line in bill.item_ids), precision_digits=4)
            bill.total_charges = float_round(base_charges, precision_digits=2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Looping Serial Number Logic (1-25)
            last_bill = self.search([], order='id desc', limit=1)
            
            if last_bill and last_bill.bill_number:
                next_num = last_bill.bill_number + 1
                if next_num > 25:
                    next_num = 1
            else:
                next_num = 1
                
            vals['bill_number'] = next_num
            # Set the Display Name properly
            vals['name'] = f"Bill #{next_num}"

        return super(CustomBill, self).create(vals_list)
    
    def action_print_bill(self):
        # Ensure you update your XML report ID to match this if it changes
        return self.env.ref('custom_jewellery_billing.action_report_custom_bill').report_action(self, config=False)