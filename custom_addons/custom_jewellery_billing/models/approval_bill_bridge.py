from odoo import models, fields
from odoo.tools.float_utils import float_round


class JewelryApprovalBilling(models.Model):
    """Closing an approval memo turns the pieces the customer kept into a sale.

    The memo itself lives in custom_stock_barcode (the inventory module), which
    knows nothing about billing. This module — which already depends on it —
    fills in the _on_close_kept hook to raise the bill, so the dependency only
    ever points one way.
    """

    _inherit = 'jewelry.approval'

    bill_id = fields.Many2one(
        'custom.bill', string='Generated Bill', readonly=True, copy=False,
        help='Bill raised for the pieces the customer kept when this memo was closed.',
    )

    def _on_close_kept(self, kept_lines):
        self.ensure_one()
        if not kept_lines:
            return super()._on_close_kept(kept_lines)

        line_vals = []
        for line in kept_lines:
            item = line.source_item_id
            less_pp, charges_pp = item._per_piece_rates()
            line_vals.append((0, 0, {
                'name': f'{item.name} [{item.barcode}]',
                'source_item_id': item.id,
                'pieces_taken': line.pieces_kept,
                # Exactly what went out and never came back — both figures were
                # weighed, so no proration is needed. Still editable on the bill.
                'weight': float_round(line.weight - line.weight_returned, precision_digits=3),
                'less': float_round(less_pp * line.pieces_kept, precision_digits=3),
                'charges': float_round(charges_pp * line.pieces_kept, precision_digits=2),
                'touch': (item.purity.value / 100.0) if item.purity else 0.0,
                # Inventory already moved when the memo was issued.
                'from_approval': True,
            }))

        bill = self.env['custom.bill'].create({
            'partner_id': self.partner_id.id,
            'item_ids': line_vals,
            'remarks': f'Kept from approval memo {self.name}.',
        })
        self.bill_id = bill.id
        return bill

    def action_close(self):
        """After the memo is settled, drop the cashier straight onto the bill
        raised for the kept pieces so they can take payment right away."""
        res = super().action_close()
        if len(self) == 1 and self.bill_id:
            return self.action_open_bill()
        return res

    def action_open_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'custom.bill',
            'res_id': self.bill_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
