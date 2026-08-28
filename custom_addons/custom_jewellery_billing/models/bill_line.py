from odoo import models, fields, api
from odoo.tools.float_utils import float_round

class CustomBillLine(models.Model):
    _name = 'custom.bill.line'
    _description = 'Jewelry Bill Line Item'

    # --- The Invisible Link Back to the Header ---
    bill_id = fields.Many2one('custom.bill', string='Bill Reference',readonly=True,ondelete='cascade')

    # --- Line Item Fields ---
    name = fields.Char(string='Name', required=True)
    weight = fields.Float(string='Weight', digits=(16, 4))
    less = fields.Float(string='Less', digits=(16, 4))
    melting = fields.Float(string='Melting')
    touch = fields.Float(string='Touch')
    pure = fields.Float(
        string="Pure",
        compute="_compute_pure",
        store=True,
        digits=(16, 4)
    )
    charges = fields.Float(string='Charges')
    net_weight = fields.Float(
        compute="_compute_net_weight",
        store=True,
        digits=(16, 4)
    )

    # --- Inventory link (scan-to-bill / tag splitting) ---
    source_item_id = fields.Many2one(
        'jewelry.barcode.item', string='Tag', ondelete='restrict', copy=False,
        help='Inventory tag this line was scanned from. Saving the bill takes '
             'the pieces and weight below out of that tag.',
    )
    pieces_taken = fields.Integer(
        string='Pcs', default=0,
        help='How many of the tag\'s pieces the customer is buying. Lower it for '
             'a partial sale — the rest stays on the same tag.',
    )
    from_approval = fields.Boolean(
        string='From Approval', default=False, readonly=True, copy=False,
        help='Generated when an approval memo was closed. The memo already moved '
             'this stock, so the line never touches inventory again.',
    )

    @api.depends('weight', 'less')
    def _compute_net_weight(self):
        for line in self:
            line.net_weight = line.weight - line.less

    @api.depends('weight', 'less', 'touch')
    def _compute_pure(self):
        for line in self:
            net_weight = line.weight - line.less
            line.pure = net_weight * (line.touch / 100.0)

    # ── Tag splitting ─────────────────────────────────────────────────────────

    @api.onchange('pieces_taken')
    def _onchange_pieces_taken(self):
        """Selling part of a lot scales the line by the same pieces ratio: 3 of
        4 pieces carry 3/4 of the weight, less and charges.

        Every field stays editable — this only seeds them. The weight in
        particular is a guess (pieces of a lot are rarely equal), so put the
        pieces on the scale and type what they actually weigh.
        """
        if not self.source_item_id or self.from_approval:
            return
        item = self.source_item_id
        less_pp, charges_pp = item._per_piece_rates()
        self.weight = float_round(item._per_piece_weight() * self.pieces_taken, precision_digits=3)
        self.less = float_round(less_pp * self.pieces_taken, precision_digits=3)
        self.charges = float_round(charges_pp * self.pieces_taken, precision_digits=2)

    def _sync_inventory(self, d_pieces, d_weight, item=None):
        """Push a consumption delta to the linked tag. Approval-generated lines
        are inert: the memo owns that stock movement."""
        self.ensure_one()
        if self.from_approval or self.env.context.get('skip_inventory_sync'):
            return
        item = item if item is not None else self.source_item_id
        if not item or (not d_pieces and not d_weight):
            return
        item._apply_consumption(d_pieces, d_weight)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            line._sync_inventory(line.pieces_taken, line.weight)
        return lines

    def write(self, vals):
        tracked = {'source_item_id', 'pieces_taken', 'weight'}
        if not tracked & set(vals):
            return super().write(vals)
        # Snapshot before the write so we can send the tag an exact delta.
        before = {
            line.id: (line.source_item_id, line.pieces_taken, line.weight)
            for line in self
        }
        res = super().write(vals)
        for line in self:
            old_item, old_pieces, old_weight = before[line.id]
            if old_item == line.source_item_id:
                line._sync_inventory(
                    line.pieces_taken - old_pieces, line.weight - old_weight,
                )
            else:
                # Re-pointed at a different tag: give the old one everything back.
                line._sync_inventory(-old_pieces, -old_weight, item=old_item)
                line._sync_inventory(line.pieces_taken, line.weight)
        return res

    def unlink(self):
        for line in self:
            line._sync_inventory(-line.pieces_taken, -line.weight)
        return super().unlink()
