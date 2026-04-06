from odoo import models, fields, api
print("🔥 BILL.PY LOADED")
    
class CustomBill(models.Model):
    _name = 'custom.bill'
    _description = 'Jewelry Bill'

    # --- Header Fields ---
    name = fields.Char(string='Reference', required=True, copy=False, default='New')
    serial_number = fields.Integer(string='Serial Number', readonly=True, copy=False)
    date = fields.Date(string='Date', default=fields.Date.context_today)
    customer_id = fields.Many2one('res.partner', string='Customer')

    # --- The Relational Table ---
    # This creates the table that holds the line items
    item_ids = fields.One2many('custom.bill.line', 'bill_id', string='Bill Items')

    # --- The Totals (Computed automatically) ---
    total_weight = fields.Float(string='Total Weight', compute='_compute_totals', store=True, digits=(16, 3))
    total_pure = fields.Float(string='Total Pure', compute='_compute_totals', store=True, digits=(16, 3))
    total_net_weight = fields.Float(string='Total Net Weight', compute='_compute_totals', store=True, digits=(16, 3))
    total_charges = fields.Float(string='Total Charges', compute='_compute_totals', store=True)
    total_less = fields.Float(string='Total Less', compute='_compute_totals', store=True, digits=(16, 3))

    rate_cut = fields.Integer(string='Rate', store=True, default=0, readonly=False)
    # --- Python Logic: Calculate Totals ---
    @api.depends('item_ids.weight', 'item_ids.pure', 'item_ids.charges', 'rate_cut')
    def _compute_totals(self):
        for bill in self:
            # Native Python math instantly calculates the table without crashing wkhtmltopdf
            bill.total_weight = sum(bill.item_ids.mapped('weight'))
            bill.total_pure = sum(bill.item_ids.mapped('pure'))
            bill.total_charges = sum(bill.item_ids.mapped('charges'))
            bill.total_net_weight = sum(bill.item_ids.mapped('net_weight'))
            bill.total_less = sum(bill.item_ids.mapped('less'))

            if bill.rate_cut > 0:
                bill.total_charges = (bill.total_pure * bill.rate_cut) + bill.total_charges
                bill.total_pure = 0

    # --- Python Logic: The 1-to-25 Looping Serial Number ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Find the very last bill created in the database
            last_bill = self.search([], order='id desc', limit=1)
            
            if last_bill and last_bill.serial_number:
                next_num = last_bill.serial_number + 1
                if next_num > 25:
                    next_num = 1
            else:
                next_num = 1
                
            vals['serial_number'] = next_num

        # Save the record
        return super(CustomBill, self).create(vals_list)
    
    def action_print_bill(self):
        return self.env.ref('custom_jewellery_billing.action_report_custom_bill').report_action(self, config=False)