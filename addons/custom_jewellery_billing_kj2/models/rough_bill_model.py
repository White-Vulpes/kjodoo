from odoo import models, fields, api
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)

class RoughBill(models.Model):
    _name = 'custom.rough.bill2'
    _description = 'Rough Bill'
    _rec_name = 'name'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Rough Bill Reference', copy=False)
    bill_number = fields.Integer(string='Bill Number', copy=False, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)

    item_ids = fields.One2many('custom.rough.bill2.line', 'bill_id', string='Bill Items', tracking=True)

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

    transaction_ids = fields.One2many('custom.rough.bill2.transaction', 'bill_id', string='Transactions', tracking=True)

    balance_pure = fields.Float(string='Remaining Pure', compute='_compute_balances', store=True, digits=(16, 4))
    balance_charges = fields.Float(string='Remaining Balance', compute='_compute_balances', store=True, digits=(16, 2))

    @api.depends(
        'total_pure', 'total_charges',
        'transaction_ids.ttype', 'transaction_ids.pure_weight', 'transaction_ids.amount'
    )
    def _compute_balances(self):
        for bill in self:
            running_pure = bill.total_pure
            running_charges = bill.total_charges
            for txn in bill.transaction_ids:
                if txn.ttype == 'metal_recv':
                    running_pure -= txn.pure_weight
                elif txn.ttype == 'old_item':
                    if txn.amount > 0:
                        running_charges -= txn.amount
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
                    running_charges += txn.amount
            bill.balance_pure = float_round(running_pure, precision_digits=4)
            bill.balance_charges = float_round(running_charges, precision_digits=2)

    def _compute_karat_22(self):
        for bill in self:
            rate_str = self.env['ir.config_parameter'].sudo().get_param('jewelry.gold_rate_22k', default='0')
            bill.karat_22 = float(rate_str)

    def _compute_karat_18(self):
        for bill in self:
            rate_str = self.env['ir.config_parameter'].sudo().get_param('jewelry.gold_rate_18k', default='0')
            bill.karat_18 = float(rate_str)

    @api.depends('item_ids.weight', 'item_ids.total_wt', 'item_ids.charges', 'item_ids.less', 'item_ids.net_weight', 'item_ids.pure')
    def _compute_totals(self):
        for bill in self:
            bill.total_weight = float_round(sum(line.weight for line in bill.item_ids), precision_digits=4)
            bill.total_wt = float_round(sum(line.total_wt for line in bill.item_ids), precision_digits=4)
            bill.total_pure = float_round(sum(line.pure for line in bill.item_ids), precision_digits=4)
            bill.total_less = float_round(sum(line.less for line in bill.item_ids), precision_digits=4)
            bill.total_net_weight = float_round(sum(line.net_weight for line in bill.item_ids), precision_digits=4)
            bill.total_charges = float_round(sum(line.charges for line in bill.item_ids), precision_digits=2)

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
            last = self.search([], order='id desc', limit=1)
            if last and last.bill_number:
                next_num = last.bill_number + 1
                if next_num > 25:
                    next_num = 1
            else:
                next_num = 1
            vals['bill_number'] = next_num
            vals['name'] = f"Rough #{next_num}"
        return super().create(vals_list)

    def action_print_rough_bill(self):
        report = self.env.ref('custom_jewellery_billing_kj2.action_report_rough_bill')
        report_url = f'/report/pdf/{report.report_name}/{self.id}?time={fields.Datetime.now().timestamp()}'
        return {
            'type': 'ir.actions.act_url',
            'url': report_url,
            'target': 'new',
        }

    def action_print_rough_bill_retail(self):
        report = self.env.ref('custom_jewellery_billing_kj2.action_report_rough_bill_retail')
        report_url = f'/report/pdf/{report.report_name}/{self.id}?time={fields.Datetime.now().timestamp()}'
        return {
            'type': 'ir.actions.act_url',
            'url': report_url,
            'target': 'new',
        }

    def action_import_to_bill(self):
        new_bill = self.env['custom.bill2'].create({
            'date': self.date,
            'remarks': self.remarks,
            'show_transaction': self.show_transaction,
            'karat_24': self.karat_24,
            'karat_22': self.karat_22,
            'karat_18': self.karat_18,
        })
        for line in self.item_ids:
            self.env['custom.bill2.line'].create({
                'bill_id': new_bill.id,
                'name': line.name,
                'weight': line.weight,
                'less': line.less,
                'melting': line.melting,
                'touch': line.touch,
                'VAT': line.VAT,
                'type': line.type,
                'charges': line.charges,
            })
        for txn in self.transaction_ids:
            self.env['custom.bill2.transaction'].create({
                'bill_id': new_bill.id,
                'date': txn.date,
                'ttype': txn.ttype,
                'gross_weight': txn.gross_weight,
                'less': txn.less,
                'purity': txn.purity,
                'pure_weight': txn.pure_weight,
                'rate': txn.rate,
                'amount': txn.amount,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Jewelry Bill',
            'res_model': 'custom.bill2',
            'res_id': new_bill.id,
            'view_mode': 'form',
            'target': 'current',
        }
