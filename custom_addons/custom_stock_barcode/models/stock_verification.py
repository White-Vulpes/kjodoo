from odoo import models, fields, api
from odoo.exceptions import UserError


class JewelryStockVerification(models.Model):
    _name = 'jewelry.stock.verification'
    _description = 'Stock Verification Session'
    _order = 'date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    date = fields.Date(string='Verification Date', default=fields.Date.context_today, required=True)
    user_id = fields.Many2one('res.users', string='Verified By', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], string='Status', default='draft', readonly=True)
    notes = fields.Text(string='Notes')

    line_ids = fields.One2many('jewelry.stock.verification.line', 'verification_id', string='Items')

    # Non-stored scan fields (UI only)
    scan_barcode = fields.Char(string='Scan Barcode', store=False)
    last_scan_result = fields.Char(string='Last Scan Result', store=False)

    # Computed stats
    total_count = fields.Integer(string='Total Items', compute='_compute_stats')
    verified_count = fields.Integer(string='Verified', compute='_compute_stats')
    missing_count = fields.Integer(string='Missing', compute='_compute_stats')
    progress_pct = fields.Float(string='Progress (%)', compute='_compute_stats', digits=(5, 1))

    @api.depends('line_ids.is_verified')
    def _compute_stats(self):
        for rec in self:
            total = len(rec.line_ids)
            verified = len(rec.line_ids.filtered('is_verified'))
            rec.total_count = total
            rec.verified_count = verified
            rec.missing_count = total - verified
            rec.progress_pct = (verified / total * 100) if total else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('jewelry.stock.verification') or 'New'
        records = super().create(vals_list)
        for rec in records:
            rec._generate_lines()
        return records

    def _generate_lines(self):
        self.ensure_one()
        self.line_ids.unlink()
        items = self.env['jewelry.barcode.item'].search([('active', '=', True)])
        line_vals = [{'verification_id': self.id, 'item_id': item.id} for item in items]
        if line_vals:
            self.env['jewelry.stock.verification.line'].create(line_vals)

    def action_start(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError('No items found. Please ensure there are active inventory items before starting.')
        self.state = 'in_progress'

    def action_complete(self):
        self.ensure_one()
        self.state = 'done'

    def action_reset(self):
        self.ensure_one()
        self.state = 'draft'
        self._generate_lines()

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('custom_stock_barcode.action_report_stock_verification').report_action(self)

    @api.onchange('scan_barcode')
    def _onchange_scan_barcode(self):
        if not self.scan_barcode:
            return
        barcode = self.scan_barcode.strip()
        matched = self.line_ids.filtered(lambda l: l.barcode == barcode)
        if matched:
            line = matched[0]
            if line.is_verified:
                self.last_scan_result = f'Already verified: {line.item_name} ({barcode})'
            else:
                line.is_verified = True
                line.verified_date = fields.Datetime.now()
                self.last_scan_result = f'Found: {line.item_name} ({barcode})'
        else:
            self.last_scan_result = f'Not found in session: {barcode}'
        self.scan_barcode = ''


class JewelryStockVerificationLine(models.Model):
    _name = 'jewelry.stock.verification.line'
    _description = 'Stock Verification Line'
    _order = 'is_verified asc, item_name asc'

    verification_id = fields.Many2one('jewelry.stock.verification', string='Session', required=True, ondelete='cascade')
    item_id = fields.Many2one('jewelry.barcode.item', string='Item', required=True, ondelete='cascade')

    barcode = fields.Char(related='item_id.barcode', store=True, string='Barcode')
    item_name = fields.Char(related='item_id.name', store=True, string='Item Name')
    category_id = fields.Many2one('jewelry.category', related='item_id.category', store=True, string='Category')
    purity_id = fields.Many2one('jewelry.purity', related='item_id.purity', store=True, string='Purity')
    weight = fields.Float(related='item_id.weight', store=True, string='Weight (g)', digits=(16, 3))

    is_verified = fields.Boolean(string='Found', default=False)
    verified_date = fields.Datetime(string='Verified At')
    line_notes = fields.Char(string='Notes')

    @api.onchange('is_verified')
    def _onchange_is_verified(self):
        if self.is_verified and not self.verified_date:
            self.verified_date = fields.Datetime.now()
        elif not self.is_verified:
            self.verified_date = False
