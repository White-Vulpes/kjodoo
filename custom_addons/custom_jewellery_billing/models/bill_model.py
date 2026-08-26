from odoo import models, fields, api
from odoo.tools.float_utils import float_round
import logging
import requests
import re

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

    show_transaction = fields.Boolean(string="Show Transaction")

    # --- The Totals ---
    total_weight = fields.Float(string='Total Weight', compute='_compute_totals', store=True, digits=(16, 4))
    total_pure = fields.Float(string='Total Pure', compute='_compute_totals', store=True, digits=(16, 4))
    total_net_weight = fields.Float(string='Total Net Weight', compute='_compute_totals', store=True, digits=(16, 4))
    total_charges = fields.Float(string='Total Charges', compute='_compute_totals', store=True)
    total_less = fields.Float(string='Total Less', compute='_compute_totals', store=True, digits=(16, 4))

    # Add the relational field
    transaction_ids = fields.One2many('custom.bill.transaction', 'bill_id', string='Transactions')

    # Add the live balance fields
    balance_pure = fields.Float(string='Remaining Pure', compute='_compute_balances', store=True, digits=(16, 4))
    balance_charges = fields.Float(string='Remaining Balance', compute='_compute_balances', store=True, digits=(16, 0))

    remarks = fields.Text(string='Remarks')

    # Non-stored scan fields (UI only). A USB scanner types the barcode and
    # presses Enter, which fires the onchange below — no JS needed.
    scan_barcode = fields.Char(string='Scan Barcode', store=False)
    last_scan_result = fields.Char(string='Last Scan Result', store=False, readonly=True)

    @api.onchange('scan_barcode')
    def _onchange_scan_barcode(self):
        if not self.scan_barcode:
            return
        code = self.scan_barcode.strip()
        self.scan_barcode = ''
        item = self.env['jewelry.barcode.item']._find_by_barcode(code)
        if not item:
            self.last_scan_result = f'Not found: {code}'
            return
        if item.pieces <= 0:
            self.last_scan_result = f'Out of stock: {item.name} ({code})'
            return
        if any(line.source_item_id.id == item.id for line in self.item_ids):
            self.last_scan_result = f'Already on this bill: {item.name} ({code})'
            return
        self.item_ids = [(0, 0, item._prepare_bill_line_vals())]
        result = f'Added: {item.name} ({code}) — {item.pieces} pc'
        # The tag may be away at an exhibition or another shop. Selling from
        # there is the normal case, so the line still goes on the bill — but at
        # the counter this is the warning that the piece is not in the building.
        away = item.dispatch_id
        if away and away.state in ('out', 'verifying'):
            result += f' — NOTE: this tag is out on {away.name} ({away.destination})'
        self.last_scan_result = result

    def unlink(self):
        # A one2many with ondelete='cascade' is dropped at database level, which
        # would skip the bill line's own unlink and strand the stock. Delete the
        # lines explicitly so every tag gets its pieces back.
        self.mapped('item_ids').unlink()
        return super().unlink()

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
            # Round the final cash/charges balance to the nearest whole rupee
            # once every transaction has been applied.
            bill.balance_charges = float_round(running_charges, precision_digits=0)

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
        # 1. Get the report reference
        report = self.env.ref('custom_jewellery_billing.action_report_custom_bill')
        
        # 2. Construct the direct URL to the PDF
        report_url = f'/report/pdf/{report.report_name}/{self.id}?time={fields.Datetime.now().timestamp()}'
        
        # 3. Return a URL action to force a new tab
        return {
            'type': 'ir.actions.act_url',
            'url': report_url,
            'target': 'new',  # 'new' tells Odoo to open a new browser tab
        }

class JewelryGoldRate(models.AbstractModel):
    # AbstractModels don't create database tables, they are just for holding logic!
    _name = 'jewelry.gold.rate'
    _description = 'Gold Rate Scraper'

    @api.model
    def fetch_and_update_rates(self):
        endpoint = "https://production-sfo.browserless.io/chromium/bql"
        query_string = {
            "token": "RsN4qBdqAWs4QF29af15f986412011f7f7743334ab",
        }
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "query": "mutation scraping_example {\n  goto(\n    url: \"https://thejewellersassociation.org/\"\n    waitUntil: load\n    timeout: 12000\n  ) {\n    status\n  }\n  \n  posts: querySelectorAll(selector: \"span.gold_rate\", visible: true) {\n    rates: innerHTML\n  }\n}",
            "operationName": "scraping_example",
        }

        try:
            response = requests.post(endpoint, params=query_string, headers=headers, json=payload)
            data = response.json()
            raw_rates = [post.get("rates", "") for post in data.get("data", {}).get("posts", [])]

            numeric_rates = []
            for rate in raw_rates:
                clean_rate = re.sub(r'[^\d.]', '', str(rate))
                if clean_rate:
                    numeric_rates.append(float(clean_rate))

            valid_rates = sorted([r for r in numeric_rates if r > 0])

            rate_18k = valid_rates[0] if len(valid_rates) >= 1 else 0.0
            rate_22k = valid_rates[1] if len(valid_rates) >= 2 else 0.0

            # Save to System Parameters
            if rate_18k > 0:
                self.env['ir.config_parameter'].sudo().set_param('jewelry.gold_rate_18k', str(rate_18k))
            if rate_22k > 0:
                self.env['ir.config_parameter'].sudo().set_param('jewelry.gold_rate_22k', str(rate_22k))
                
            _logger.info(f"Successfully updated Gold Rates - 18K: {rate_18k}, 22K: {rate_22k}")

        except Exception as e:
            _logger.error(f"Failed to fetch gold rates. Error: {str(e)}")