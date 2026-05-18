from odoo import models, fields, api
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)

class CustomBill(models.Model):
    _name = 'custom.bill2'
    _description = 'Retail Bill'
    # This tells Odoo to use our 'name' char field as the record label
    _rec_name = 'name' 
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # This is the "Display Name" (e.g., "Bill #5")
    name = fields.Char(string='Bill Reference', required=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    
    bill_number = fields.Integer(string='Bill Number', copy=False, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)

    # --- The Relational Table ---
    item_ids = fields.One2many('custom.bill2.line', 'bill_id', string='Bill Items', tracking=True)

    # --- The Totals ---
    total_weight = fields.Float(string='Total Weight', compute='_compute_totals', store=True, digits=(16, 4))
    total_wt = fields.Float(string='Total Wt.', compute='_compute_totals', store=True, digits=(16, 4))
    total_pure = fields.Float(string='Total Pure', compute='_compute_totals', store=True, digits=(16, 4))
    total_net_weight = fields.Float(string='Total Net Weight', compute='_compute_totals', store=True, digits=(16, 4))
    total_charges = fields.Float(string='Total Charges', compute='_compute_totals', store=True)
    total_less = fields.Float(string='Total Less', compute='_compute_totals', store=True, digits=(16, 4))

    show_transaction = fields.Boolean(string="Show Transaction", tracking=True)

    remarks = fields.Text(string='Remarks', tracking=True)

    karat_24 = fields.Float(string='24K', digits=(16, 2), store=True, default=24.0, tracking=True)
    karat_22 = fields.Float(string='22K', digits=(16, 2), store=True, compute="_compute_karat_22", readonly=False, tracking=True)
    karat_18 = fields.Float(string='18K', digits=(16, 2), store=True, compute="_compute_karat_18", readonly=False, tracking=True)

    total_cash = fields.Float(string='Total Cash', compute='_compute_total_cash', store=False, digits=(16, 2))

    transaction_ids = fields.One2many('custom.bill2.transaction', 'bill_id', string='Transactions', tracking=True)

    # Add the live balance fields
    balance_pure = fields.Float(string='Remaining Pure', compute='_compute_balances', store=True, digits=(16, 4))
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
                elif txn.ttype == 'old_item':
                    if txn.amount > 0:
                        running_charges -= txn.amount  # Subtract the cash value of the old item
                    else:
                        running_pure -= txn.pure_weight
                elif txn.ttype == 'return_item':
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

            bill.balance_pure = float_round(running_pure, precision_digits=4)
            bill.balance_charges = float_round(running_charges, precision_digits=2)

    def _compute_karat_22(self):
        for bill in self:
            rate_22k_str = self.env['ir.config_parameter'].sudo().get_param('jewelry.gold_rate_22k', default='0')
            rate_22k = float(rate_22k_str)
            bill.karat_22 = rate_22k

    def _compute_karat_18(self):
        for bill in self:
            rate_18k_str = self.env['ir.config_parameter'].sudo().get_param('jewelry.gold_rate_18k', default='0')
            rate_18k = float(rate_18k_str)
            bill.karat_18 = rate_18k

    @api.depends('item_ids.weight', 'item_ids.total_wt', 'item_ids.charges', 'item_ids.less', 'item_ids.net_weight', 'item_ids.pure')
    def _compute_totals(self):
        for bill in self:
            bill.total_weight = float_round(sum(line.weight for line in bill.item_ids), precision_digits=4)
            bill.total_wt = float_round(sum(line.total_wt for line in bill.item_ids), precision_digits=4)
            bill.total_pure = float_round(sum(line.pure for line in bill.item_ids), precision_digits=4)
            bill.total_less = float_round(sum(line.less for line in bill.item_ids), precision_digits=4)
            bill.total_net_weight = float_round(sum(line.net_weight for line in bill.item_ids), precision_digits=4)
            base_charges = float_round(sum(line.charges for line in bill.item_ids), precision_digits=4)
            bill.total_charges = float_round(base_charges, precision_digits=2)

    @api.depends('total_wt', 'karat_22', 'karat_18', 'item_ids')
    def _compute_total_cash(self):
        for bill in self:
            bill.total_cash = 0.0
            for line in bill.item_ids:
                if line.type == '22K':
                    bill.total_cash += float_round(line.total_wt * bill.karat_22 + line.charges, precision_digits=2)
                elif line.type == '18K':
                    bill.total_cash += float_round(line.total_wt * bill.karat_18 + line.charges, precision_digits=2)
        
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
        # 1. Get the report reference
        report = self.env.ref('custom_jewellery_billing_kj2.action_report_custom_bill')

        # 2. Construct the direct URL to the PDF
        report_url = f'/report/pdf/{report.report_name}/{self.id}?time={fields.Datetime.now().timestamp()}'
        
        # 3. Return a URL action to force a new tab
        return {
            'type': 'ir.actions.act_url',
            'url': report_url,
            'target': 'new',  # 'new' tells Odoo to open a new browser tab
        }
    
    def action_print_bill_retail(self):
        # 1. Get the report reference
        report = self.env.ref('custom_jewellery_billing_kj2.action_report_custom_bill_retail')

        # 2. Construct the direct URL to the PDF
        report_url = f'/report/pdf/{report.report_name}/{self.id}?time={fields.Datetime.now().timestamp()}'

        # 3. Return a URL action to force a new tab
        return {
            'type': 'ir.actions.act_url',
            'url': report_url,
            'target': 'new',  # 'new' tells Odoo to open a new browser tab
        }