from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_round


class JewelryApproval(models.Model):
    """Items given on approval ("jangad"): the customer walks out with the
    goods, which leaves inventory, but nothing is sold yet. Whatever comes back
    is restored to stock; whatever is kept is a sale — see _on_close_kept."""

    _name = 'jewelry.approval'
    _description = 'Items Given on Approval (Sale or Return)'
    _order = 'date_issued desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    user_id = fields.Many2one('res.users', string='Issued By', default=lambda self: self.env.user)
    date_issued = fields.Date(string='Issue Date', default=fields.Date.context_today, required=True)
    date_closed = fields.Date(string='Closed On', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', readonly=True, copy=False)

    line_ids = fields.One2many('jewelry.approval.line', 'approval_id', string='Items')
    remarks = fields.Text(string='Remarks')

    # Non-stored scan fields (UI only)
    scan_barcode = fields.Char(string='Scan Barcode', store=False)
    last_scan_result = fields.Char(string='Last Scan Result', store=False, readonly=True)

    total_taken = fields.Integer(string='Pieces Taken', compute='_compute_totals')
    total_returned = fields.Integer(string='Pieces Returned', compute='_compute_totals')
    total_kept = fields.Integer(string='Pieces Kept', compute='_compute_totals')

    # Gross weight the same way, so the memo shows how much metal is out on
    # approval, how much came back, and how much the customer kept.
    total_weight_taken = fields.Float(
        string='Weight Out', digits=(16, 3), compute='_compute_totals')
    total_weight_returned = fields.Float(
        string='Weight Back', digits=(16, 3), compute='_compute_totals')
    total_weight_kept = fields.Float(
        string='Weight Kept', digits=(16, 3), compute='_compute_totals')

    @api.depends('line_ids.pieces_taken', 'line_ids.pieces_returned',
                 'line_ids.weight', 'line_ids.weight_returned')
    def _compute_totals(self):
        for memo in self:
            memo.total_taken = sum(memo.line_ids.mapped('pieces_taken'))
            memo.total_returned = sum(memo.line_ids.mapped('pieces_returned'))
            memo.total_kept = memo.total_taken - memo.total_returned
            memo.total_weight_taken = float_round(
                sum(memo.line_ids.mapped('weight')), precision_digits=3)
            memo.total_weight_returned = float_round(
                sum(memo.line_ids.mapped('weight_returned')), precision_digits=3)
            memo.total_weight_kept = float_round(
                memo.total_weight_taken - memo.total_weight_returned, precision_digits=3)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('jewelry.approval') or 'New'
        return super().create(vals_list)

    @api.onchange('scan_barcode')
    def _onchange_scan_barcode(self):
        if not self.scan_barcode:
            return
        code = self.scan_barcode.strip()
        self.scan_barcode = ''
        if self.state != 'draft':
            self.last_scan_result = 'Memo is no longer a draft — items cannot be added.'
            return
        item = self.env['jewelry.barcode.item']._find_by_barcode(code)
        if not item:
            self.last_scan_result = f'Not found: {code}'
            return
        if item.pieces <= 0:
            self.last_scan_result = f'Out of stock: {item.name} ({code})'
            return
        if any(line.source_item_id.id == item.id for line in self.line_ids):
            self.last_scan_result = f'Already on this memo: {item.name} ({code})'
            return
        self.line_ids = [(0, 0, item._prepare_approval_line_vals())]
        self.last_scan_result = f'Added: {item.name} ({code}) — {item.pieces} pc'

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def action_issue(self):
        """Hand the goods over: deplete inventory, snapshot each line's share of
        the tag's weight / less / charges. This is not a sale."""
        for memo in self:
            if memo.state != 'draft':
                raise UserError('Only a draft memo can be issued.')
            if not memo.line_ids:
                raise UserError('Add at least one item before issuing this memo.')
            for line in memo.line_ids:
                item = line.source_item_id
                if line.pieces_taken <= 0:
                    raise UserError(f'Set the pieces to take for {item.name} ({item.barcode}).')
                if line.pieces_taken > item.pieces:
                    raise UserError(
                        f'Tag {item.barcode} ({item.name}) only has {item.pieces} piece(s) '
                        f'in stock; cannot issue {line.pieces_taken}.'
                    )
                # The weight that leaves is whatever was weighed on the line.
                # Pieces of a lot are rarely equal, so a prorated figure is only
                # ever the suggestion the line was seeded with.
                if (line.pieces_taken < item.pieces
                        and float_compare(item.weight, 0.0, precision_digits=3) > 0
                        and float_compare(line.weight, 0.0, precision_digits=3) <= 0):
                    raise UserError(
                        f'Weigh the {line.pieces_taken} piece(s) being taken from tag '
                        f'{item.barcode} ({item.name}) and enter their gross weight.'
                    )
                item._apply_consumption(line.pieces_taken, line.weight)
            memo.state = 'issued'

    def action_register_return(self):
        """Push whatever `pieces_returned` now says back into stock. Safe to run
        repeatedly: each line tracks how much it has already restored."""
        for memo in self:
            if memo.state != 'issued':
                raise UserError('Returns can only be registered on an issued memo.')
            for line in memo.line_ids:
                line._restore_returned()

    def action_close(self):
        """Settle the memo: returns are flushed and the kept pieces — which are
        still out of stock — become a sale via the _on_close_kept hook."""
        for memo in self:
            if memo.state != 'issued':
                raise UserError('Only an issued memo can be closed.')
            for line in memo.line_ids:
                line._restore_returned()
            kept = memo.line_ids.filtered(lambda l: l.pieces_kept > 0)
            memo._on_close_kept(kept)
            memo.write({'state': 'closed', 'date_closed': fields.Date.context_today(memo)})

    def _on_close_kept(self, kept_lines):
        """Hook — kept pieces are a sale.

        In this module they simply stay depleted from inventory. Installing
        custom_jewellery_billing overrides this to raise a Jewelry Bill for the
        customer.
        """
        return False

    def action_cancel(self):
        """Call the whole memo off: everything still out comes back to stock."""
        for memo in self:
            if memo.state not in ('draft', 'issued'):
                raise UserError('Only a draft or issued memo can be cancelled.')
            if memo.state == 'issued':
                # Nothing was sold, so everything goes back exactly as it left.
                for line in memo.line_ids:
                    line.write({
                        'pieces_returned': line.pieces_taken,
                        'weight_returned': line.weight,
                    })
                    line._restore_returned()
            memo.state = 'cancelled'

    def action_reset_to_draft(self):
        for memo in self:
            if memo.state != 'cancelled':
                raise UserError('Only a cancelled memo can be reset to draft.')
            memo.state = 'draft'


class JewelryApprovalLine(models.Model):
    _name = 'jewelry.approval.line'
    _description = 'Approval Memo Line'
    _order = 'id'

    approval_id = fields.Many2one(
        'jewelry.approval', string='Memo', required=True, ondelete='cascade',
    )
    source_item_id = fields.Many2one(
        'jewelry.barcode.item', string='Tag', required=True, ondelete='restrict',
    )
    barcode = fields.Char(related='source_item_id.barcode', string='Barcode', store=True, readonly=True)
    item_name = fields.Char(related='source_item_id.name', string='Item', store=True, readonly=True)
    state = fields.Selection(related='approval_id.state', string='Status', readonly=True)

    pieces_taken = fields.Integer(string='Pieces Taken', default=1, required=True)
    pieces_returned = fields.Integer(string='Pieces Returned', default=0)
    pieces_kept = fields.Integer(string='Pieces Kept', compute='_compute_pieces_kept', store=True)

    # Weighed on the way out. Seeded per-piece from the tag, then overwritten
    # with what the scale says — pieces of a lot are rarely equal.
    weight = fields.Float(string='Weight Out', digits=(16, 3))
    less = fields.Float(string='Less', digits=(16, 3))
    charges = fields.Float(string='Charges', digits=(16, 2))

    # Weighed on the way back in, for the same reason.
    weight_returned = fields.Float(string='Weight Returned', digits=(16, 3))

    # How much has actually been pushed back into stock so far, so repeated
    # partial returns never double-restore or drift.
    pieces_restored = fields.Integer(string='Pieces Restored', default=0, readonly=True, copy=False)
    weight_restored = fields.Float(string='Weight Restored', digits=(16, 3), readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        # Rows may only be added while the memo is still a draft: once issued,
        # every line corresponds to stock that has physically left.
        for line in lines:
            if line.approval_id.state != 'draft':
                raise UserError(
                    'Items can only be added to an approval memo while it is a draft.'
                )
        return lines

    def unlink(self):
        for line in self:
            if line.approval_id.state == 'issued' and line.pieces_kept:
                raise UserError(
                    f'{line.barcode} is still out on this memo. Register its return '
                    f'before removing the line.'
                )
        return super().unlink()

    @api.onchange('pieces_taken')
    def _onchange_pieces_taken(self):
        """Seed the line from the tag at the pieces ratio. Suggestions only —
        weigh the pieces and correct the gross weight before issuing."""
        if not self.source_item_id:
            return
        item = self.source_item_id
        less_pp, charges_pp = item._per_piece_rates()
        self.weight = float_round(item._per_piece_weight() * self.pieces_taken, precision_digits=3)
        self.less = float_round(less_pp * self.pieces_taken, precision_digits=3)
        self.charges = float_round(charges_pp * self.pieces_taken, precision_digits=2)

    @api.onchange('pieces_returned')
    def _onchange_pieces_returned(self):
        """Same idea coming back: suggest the returned pieces' share of what
        went out, then weigh them and correct it."""
        if not self.pieces_taken:
            return
        self.weight_returned = float_round(
            self.weight * self.pieces_returned / self.pieces_taken, precision_digits=3,
        )

    @api.depends('pieces_taken', 'pieces_returned')
    def _compute_pieces_kept(self):
        for line in self:
            line.pieces_kept = line.pieces_taken - line.pieces_returned

    @api.constrains('pieces_returned', 'pieces_taken', 'weight_returned', 'weight')
    def _check_returned(self):
        for line in self:
            if line.pieces_returned < 0 or line.pieces_returned > line.pieces_taken:
                raise ValidationError(
                    f'Returned pieces for {line.barcode} must be between 0 and '
                    f'{line.pieces_taken}.'
                )
            if float_compare(line.weight_returned, line.weight, precision_digits=3) > 0:
                raise ValidationError(
                    f'{line.weight_returned:.3f} g cannot come back from tag '
                    f'{line.barcode}; only {line.weight:.3f} g went out.'
                )

    def _restore_returned(self):
        """Put the not-yet-restored share of the returned pieces back on the tag.
        `weight_returned` is cumulative, so it is compared against what has
        already gone back rather than added blindly — restoring everything then
        lands exactly on the issued weight."""
        for line in self:
            d_pieces = line.pieces_returned - line.pieces_restored
            if not d_pieces:
                continue
            target_weight = line.weight_returned
            d_weight = float_round(target_weight - line.weight_restored, precision_digits=3)
            line.source_item_id._apply_consumption(-d_pieces, -d_weight)
            line.write({
                'pieces_restored': line.pieces_returned,
                'weight_restored': target_weight,
            })
