from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round


# States in which a dispatch still physically holds the goods, so its tags are
# unavailable to anyone else.
OPEN_STATES = ('out', 'verifying')


class JewelryDispatch(models.Model):
    """Stock we take out ourselves: an exhibition, a route, or another of our
    own shops.

    This is deliberately *not* an approval memo. On approval the customer walks
    out with the goods and inventory drops; here the goods are still ours, so
    nothing is consumed — each tag keeps its pieces and weight and is simply
    flagged as being away (`jewelry.barcode.item.dispatch_id`).

    That one decision makes the rest fall out:

    * Selling at the venue needs no special handling. The cashier scans the tag
      into an ordinary bill, the shared consumption engine lowers it, and
      `pieces_sold` below is just `pieces_out - tag.pieces`.
    * A shop-floor Stock Verification skips tags that are away instead of
      reporting hundreds of them missing.
    * Coming back, every tag is scanned in a Stock Verification session scoped
      to this dispatch; anything that fails to turn up is a shortage.

    Because the flag lives on the tag, a tag travels as a whole lot — you
    cannot send 2 of a 4-piece tag and leave 2 behind.
    """

    _name = 'jewelry.dispatch'
    _description = 'Stock Taken Out (Exhibition / Route / Shop)'
    _order = 'date_out desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    dispatch_type = fields.Selection([
        ('exhibition', 'Exhibition'),
        ('shop', 'Other Shop'),
        ('route', 'Route'),
        ('other', 'Other'),
    ], string='Type', default='exhibition', required=True)
    destination = fields.Char(
        string='Destination', required=True,
        help='Venue, shop or route the goods are going to.',
    )
    partner_id = fields.Many2one(
        'res.partner', string='Host / Shop',
        help='Optional: the shop or party hosting the goods. This is not a '
             'customer — nothing here is a sale.',
    )
    user_id = fields.Many2one(
        'res.users', string='Taken By', default=lambda self: self.env.user,
    )
    date_out = fields.Date(string='Date Out', default=fields.Date.context_today, required=True)
    date_due = fields.Date(string='Expected Back')
    date_closed = fields.Date(string='Closed On', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('out', 'Out'),
        ('verifying', 'Verifying Return'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', readonly=True, copy=False)

    line_ids = fields.One2many('jewelry.dispatch.line', 'dispatch_id', string='Tags')
    verification_id = fields.Many2one(
        'jewelry.stock.verification', string='Return Check',
        readonly=True, copy=False,
        help='Stock Verification session used to scan the goods back in.',
    )
    verification_applied = fields.Boolean(
        string='Return Check Applied', readonly=True, copy=False,
        help='Set once the return check result has been pulled onto the lines. '
             'Closing will not overwrite a manual correction made afterwards.',
    )
    remarks = fields.Text(string='Remarks')

    # Non-stored scan fields (UI only). A USB scanner types the barcode and
    # presses Enter, which fires the onchange below — no JS needed.
    scan_barcode = fields.Char(string='Scan Barcode', store=False)
    last_scan_result = fields.Char(string='Last Scan Result', store=False, readonly=True)

    total_tags = fields.Integer(string='Tags', compute='_compute_totals')
    total_pieces_out = fields.Integer(string='Pieces Out', compute='_compute_totals')
    total_weight_out = fields.Float(
        string='Weight Out', digits=(16, 3), compute='_compute_totals')
    total_pieces_sold = fields.Integer(string='Pieces Sold', compute='_compute_totals')
    total_pieces_expected = fields.Integer(string='Pieces Expected Back', compute='_compute_totals')
    total_pieces_back = fields.Integer(string='Pieces Back', compute='_compute_totals')
    total_pieces_missing = fields.Integer(string='Pieces Missing', compute='_compute_totals')
    total_weight_missing = fields.Float(
        string='Weight Missing', digits=(16, 3), compute='_compute_totals')
    has_shortage = fields.Boolean(string='Has Shortage', compute='_compute_totals')

    @api.depends('state', 'line_ids.pieces_out', 'line_ids.weight_out',
                 'line_ids.pieces_sold', 'line_ids.pieces_expected',
                 'line_ids.pieces_returned', 'line_ids.pieces_missing',
                 'line_ids.missing_weight')
    def _compute_totals(self):
        for memo in self:
            lines = memo.line_ids
            memo.total_tags = len(lines)
            memo.total_pieces_out = sum(lines.mapped('pieces_out'))
            memo.total_weight_out = float_round(
                sum(lines.mapped('weight_out')), precision_digits=3)
            memo.total_pieces_sold = sum(lines.mapped('pieces_sold'))
            memo.total_pieces_expected = sum(lines.mapped('pieces_expected'))
            memo.total_pieces_back = sum(lines.mapped('pieces_returned'))
            memo.total_pieces_missing = sum(lines.mapped('pieces_missing'))
            memo.total_weight_missing = float_round(
                sum(lines.mapped('missing_weight')), precision_digits=3)
            # Only a closed dispatch can be short. While the goods are still
            # out, or half-way through the return scan, "missing" just means
            # "not counted back in yet".
            memo.has_shortage = memo.state == 'closed' and memo.total_pieces_missing > 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('jewelry.dispatch') or 'New'
        return super().create(vals_list)

    @api.onchange('scan_barcode')
    def _onchange_scan_barcode(self):
        if not self.scan_barcode:
            return
        code = self.scan_barcode.strip()
        self.scan_barcode = ''
        if self.state != 'draft':
            self.last_scan_result = 'This dispatch has already gone out — tags cannot be added.'
            return
        item = self.env['jewelry.barcode.item']._find_by_barcode(code)
        if not item:
            self.last_scan_result = f'Not found: {code}'
            return
        if item.pieces <= 0:
            self.last_scan_result = f'Out of stock: {item.name} ({code})'
            return
        if any(line.source_item_id.id == item.id for line in self.line_ids):
            self.last_scan_result = f'Already on this dispatch: {item.name} ({code})'
            return
        held_by = item.dispatch_id
        if held_by and held_by.state in OPEN_STATES and held_by.id != self._origin.id:
            self.last_scan_result = (
                f'Already out on {held_by.name} ({held_by.destination}): '
                f'{item.name} ({code})'
            )
            return
        self.line_ids = [(0, 0, item._prepare_dispatch_line_vals())]
        self.last_scan_result = f'Added: {item.name} ({code}) — {item.pieces} pc'

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def action_dispatch(self):
        """Send the goods out. Nothing is consumed: every tag keeps its pieces
        and weight and is merely flagged as being away."""
        for memo in self:
            if memo.state != 'draft':
                raise UserError('Only a draft dispatch can be sent out.')
            if not memo.line_ids:
                raise UserError('Scan at least one tag before sending this dispatch out.')
            for line in memo.line_ids:
                item = line.source_item_id
                if item.pieces <= 0:
                    raise UserError(
                        f'Tag {item.barcode} ({item.name}) has no pieces left in stock.'
                    )
                held_by = item.dispatch_id
                if held_by and held_by.state in OPEN_STATES and held_by != memo:
                    raise UserError(
                        f'Tag {item.barcode} ({item.name}) is already out on '
                        f'{held_by.name} ({held_by.destination}).'
                    )
                # The whole tag travels, so the snapshot is simply what is on it
                # at this moment — taken again here in case stock moved between
                # scanning and dispatching.
                line.write({'pieces_out': item.pieces, 'weight_out': item.weight})
                item.sudo().write({'dispatch_id': memo.id})
            memo.state = 'out'

    def action_start_return_check(self):
        """Open a Stock Verification session holding only this dispatch's tags,
        so the goods can be scanned back in on the screen staff already know."""
        self.ensure_one()
        if self.state not in OPEN_STATES:
            raise UserError('A return check can only be started on a dispatch that is out.')
        session = self.verification_id
        if not session:
            session = self.env['jewelry.stock.verification'].create({
                'dispatch_id': self.id,
                'user_id': self.env.user.id,
            })
            self.verification_id = session
        # Everything may already have been sold at the venue, leaving nothing to
        # scan; action_start would refuse that, and rightly so.
        if session.state == 'draft' and session.line_ids:
            session.action_start()
        if self.state != 'verifying':
            self.state = 'verifying'
        return {
            'type': 'ir.actions.act_window',
            'name': f'Return Check — {self.name}',
            'res_model': 'jewelry.stock.verification',
            'res_id': session.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_apply_verification(self):
        """Pull the return check's result onto the lines: a tag that was scanned
        came back whole, one that was not is short."""
        for memo in self:
            session = memo.verification_id
            if not session:
                raise UserError('Start the return check before applying its result.')
            if session.state == 'draft' and session.line_ids:
                raise UserError(
                    f'Return check {session.name} has not been started yet.'
                )
            found = set(session.line_ids.filtered('is_verified').mapped('item_id').ids)
            for line in memo.line_ids:
                line.pieces_returned = (
                    line.pieces_expected if line.source_item_id.id in found else 0
                )
            memo.verification_applied = True

    def action_close(self):
        """Settle the dispatch: apply the return check, freeze the reconciliation
        and hand every tag back to ordinary circulation."""
        for memo in self:
            if memo.state not in OPEN_STATES:
                raise UserError('Only a dispatch that is out can be closed.')
            if not memo.verification_id:
                raise UserError(
                    'Run the return check before closing this dispatch — press '
                    '"Start Return Check" and scan the goods back in.'
                )
            # Do not clobber a correction someone typed after applying it.
            if not memo.verification_applied:
                memo.action_apply_verification()
            # Freeze what the tags hold right now. Once the flag is dropped they
            # can be sold at the counter, and that must not retroactively change
            # what this memo says came back.
            for line in memo.line_ids:
                item = line.source_item_id
                line.write({
                    'pieces_snapshot': item.pieces,
                    'weight_snapshot': item.weight,
                })
            memo._clear_dispatch_flags()
            memo.write({
                'state': 'closed',
                'date_closed': fields.Date.context_today(memo),
            })

    def action_write_off_missing(self):
        """Take the shortage out of stock. Deliberately a separate, confirmed
        step: a tag found next week should simply never be written off."""
        for memo in self:
            if memo.state != 'closed':
                raise UserError(
                    'Missing stock can only be written off on a closed dispatch.'
                )
            short = memo.line_ids.filtered(
                lambda l: l.pieces_missing > 0 and not l.written_off
            )
            if not short:
                raise UserError('There is nothing left to write off on this dispatch.')
            for line in short:
                line._write_off_missing()

    def action_cancel(self):
        """Call the dispatch off. Nothing was ever consumed, so this only drops
        the away flags."""
        for memo in self:
            if memo.state not in ('draft',) + OPEN_STATES:
                raise UserError('Only a draft or open dispatch can be cancelled.')
            if memo.state != 'draft':
                for line in memo.line_ids:
                    item = line.source_item_id
                    line.write({
                        'pieces_snapshot': item.pieces,
                        'weight_snapshot': item.weight,
                    })
                memo._clear_dispatch_flags()
            memo.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        for memo in self:
            if memo.state != 'cancelled':
                raise UserError('Only a cancelled dispatch can be reset to draft.')
            memo.write({'state': 'draft'})

    def action_open_verification(self):
        self.ensure_one()
        if not self.verification_id:
            raise UserError('No return check has been started for this dispatch.')
        return {
            'type': 'ir.actions.act_window',
            'name': f'Return Check — {self.name}',
            'res_model': 'jewelry.stock.verification',
            'res_id': self.verification_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_print_dispatch(self):
        self.ensure_one()
        return self.env.ref(
            'custom_stock_barcode.action_report_jewelry_dispatch'
        ).report_action(self)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear_dispatch_flags(self):
        """Drop the away flag from every tag on this memo. A tag sold out
        completely at the venue has been archived by the consumption engine, so
        turn active_test off or it never gets its flag cleared."""
        for memo in self:
            items = memo.with_context(active_test=False).line_ids.mapped('source_item_id')
            if items:
                items.sudo().write({'dispatch_id': False})


class JewelryDispatchLine(models.Model):
    _name = 'jewelry.dispatch.line'
    _description = 'Dispatch Line'
    _order = 'id'

    dispatch_id = fields.Many2one(
        'jewelry.dispatch', string='Dispatch', required=True, ondelete='cascade',
    )
    source_item_id = fields.Many2one(
        'jewelry.barcode.item', string='Tag', required=True, ondelete='restrict',
    )
    barcode = fields.Char(related='source_item_id.barcode', string='Barcode', store=True, readonly=True)
    item_name = fields.Char(related='source_item_id.name', string='Item', store=True, readonly=True)
    category_id = fields.Many2one(
        'jewelry.category', related='source_item_id.category', string='Category', readonly=True)
    purity_id = fields.Many2one(
        'jewelry.purity', related='source_item_id.purity', string='Purity', readonly=True)
    state = fields.Selection(related='dispatch_id.state', string='Status', readonly=True)

    # What was on the tag when it left. The whole lot travels, so this is the
    # tag's own figures rather than anything weighed out.
    pieces_out = fields.Integer(string='Pieces Out', readonly=True)
    weight_out = fields.Float(string='Weight Out', digits=(16, 3), readonly=True)

    # Frozen at close/cancel so a later counter sale cannot rewrite history.
    pieces_snapshot = fields.Integer(string='Pieces at Close', readonly=True, copy=False)
    weight_snapshot = fields.Float(
        string='Weight at Close', digits=(16, 3), readonly=True, copy=False)

    pieces_now = fields.Integer(string='In Stock', compute='_compute_stock_figures')
    pieces_sold = fields.Integer(string='Sold', compute='_compute_stock_figures')
    pieces_expected = fields.Integer(string='Expected Back', compute='_compute_stock_figures')

    pieces_returned = fields.Integer(string='Returned', default=0, copy=False)
    pieces_missing = fields.Integer(string='Missing', compute='_compute_pieces_missing')
    missing_weight = fields.Float(
        string='Missing Weight', digits=(16, 3), compute='_compute_pieces_missing')

    written_off = fields.Boolean(string='Written Off', readonly=True, copy=False)
    line_notes = fields.Char(string='Notes')

    @api.depends('source_item_id.pieces', 'source_item_id.weight',
                 'pieces_out', 'pieces_snapshot', 'dispatch_id.state')
    def _compute_stock_figures(self):
        for line in self:
            pieces_now, _weight_now = line._current_stock()
            line.pieces_now = pieces_now
            # Anything the tag has shed while away was sold at the venue on an
            # ordinary bill — nothing here caused it.
            line.pieces_sold = max(line.pieces_out - pieces_now, 0)
            line.pieces_expected = pieces_now

    @api.depends('pieces_expected', 'pieces_returned', 'dispatch_id.state',
                 'source_item_id.weight', 'weight_snapshot')
    def _compute_pieces_missing(self):
        for line in self:
            if line.dispatch_id.state in ('verifying', 'closed'):
                line.pieces_missing = max(line.pieces_expected - line.pieces_returned, 0)
            else:
                # Nothing has been counted back in yet, so nothing is short.
                line.pieces_missing = 0
            line.missing_weight = line._missing_weight()

    @api.constrains('pieces_returned')
    def _check_returned(self):
        for line in self:
            if line.pieces_returned < 0:
                raise ValidationError(
                    f'Returned pieces for {line.barcode} cannot be negative.'
                )
            if line.pieces_returned > line.pieces_expected:
                raise ValidationError(
                    f'{line.pieces_returned} piece(s) cannot come back from tag '
                    f'{line.barcode}; only {line.pieces_expected} were still out.'
                )

    @api.model_create_multi
    def create(self, vals_list):
        # Check before super(): once a dispatch is out, every line stands for
        # goods that have physically left the building.
        for vals in vals_list:
            memo_id = vals.get('dispatch_id')
            if memo_id and self.env['jewelry.dispatch'].browse(memo_id).state != 'draft':
                raise UserError(
                    'Tags can only be added to a dispatch while it is a draft.'
                )
        return super().create(vals_list)

    def unlink(self):
        for line in self:
            if line.dispatch_id.state not in ('draft', 'cancelled'):
                raise UserError(
                    f'{line.barcode} has already gone out on {line.dispatch_id.name}. '
                    f'Cancel the dispatch instead of removing the line.'
                )
        return super().unlink()

    def _current_stock(self):
        """(pieces, weight) the tag holds — frozen once the memo is settled."""
        self.ensure_one()
        if self.dispatch_id.state in ('closed', 'cancelled'):
            return self.pieces_snapshot, self.weight_snapshot
        item = self.source_item_id
        return item.pieces, item.weight

    def _missing_weight(self):
        """Gross weight of the shortage. A whole tag gone takes everything left
        on it; a partial shortage is only ever the per-piece estimate."""
        self.ensure_one()
        if self.pieces_missing <= 0:
            return 0.0
        pieces_now, weight_now = self._current_stock()
        if self.pieces_missing >= pieces_now:
            return float_round(weight_now, precision_digits=3)
        return float_round(
            self.source_item_id._per_piece_weight() * self.pieces_missing,
            precision_digits=3,
        )

    def _write_off_missing(self):
        self.ensure_one()
        missing = self.pieces_missing
        if missing <= 0 or self.written_off:
            return
        item = self.source_item_id
        if missing > item.pieces:
            raise UserError(
                f'Tag {self.barcode} ({item.name}) only has {item.pieces} piece(s) in '
                f'stock, so {missing} cannot be written off. Has it been sold since '
                f'this dispatch closed?'
            )
        weight = item.weight if missing == item.pieces else self._missing_weight()
        item._apply_consumption(missing, weight)
        self.written_off = True
