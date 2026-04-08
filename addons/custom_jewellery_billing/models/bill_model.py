from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class CustomBill(models.Model):
    _name = 'custom.bill'
    _description = 'Jewelry Bill'
    # This tells Odoo to use our 'name' char field as the record label
    _rec_name = 'name' 
    _order = 'id desc'

    # --- Header Fields ---
    # Renamed from 'name' to 'partner_id' to stop the Database Integer Error
    partner_id = fields.Many2one(
        'res.partner', 
        string='Contact', 
        ondelete='restrict',
        required=True,
        help="Select Customer Name"
    )
    
    # This is the "Display Name" (e.g., "Bill #5")
    name = fields.Char(string='Bill Reference', required=True, copy=False, readonly=True, default='New')
    
    bill_number = fields.Integer(string='Bill Number', copy=False, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)

    # --- The Relational Table ---
    item_ids = fields.One2many('custom.bill.line', 'bill_id', string='Bill Items')

    # --- The Totals ---
    total_weight = fields.Float(string='Total Weight', compute='_compute_totals', store=True, digits=(16, 3))
    total_pure = fields.Float(string='Total Pure', compute='_compute_totals', store=True, digits=(16, 3))
    total_net_weight = fields.Float(string='Total Net Weight', compute='_compute_totals', store=True, digits=(16, 3))
    total_charges = fields.Float(string='Total Charges', compute='_compute_totals', store=True)
    total_less = fields.Float(string='Total Less', compute='_compute_totals', store=True, digits=(16, 3))

    rate_cut = fields.Integer(string='Rate', default=0)

    @api.depends('item_ids.weight', 'item_ids.pure', 'item_ids.charges', 'item_ids.less', 'item_ids.net_weight', 'rate_cut')
    def _compute_totals(self):
        for bill in self:
            # Using sum(line.field for line in bill.item_ids) is safer than mapped for empty sets
            bill.total_weight = sum(line.weight for line in bill.item_ids)
            bill.total_pure = sum(line.pure for line in bill.item_ids)
            bill.total_less = sum(line.less for line in bill.item_ids)
            bill.total_net_weight = sum(line.net_weight for line in bill.item_ids)
            
            base_charges = sum(line.charges for line in bill.item_ids)
            
            if bill.rate_cut > 0:
                # If rate is cut, calculate charges based on purity and reset pure display
                bill.total_charges = (bill.total_pure * bill.rate_cut) + base_charges
                bill.total_pure = 0
            else:
                bill.total_charges = base_charges

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
        return self.env.ref('custom_jewellery_billing.action_report_custom_bill').report_action(self)