import base64
import io
import random
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round

_BLACKSTONE_TABLE = str.maketrans('0123456789', 'EBLACKSTON')
_MYKOTHARIZ_TABLE = str.maketrans('0123456789', 'ZMYKOTHARI')

def _encode_digits(value):
    """BLACKSTONE cipher: 0→E 1→B 2→L 3→A 4→C 5→K 6→S 7→T 8→O 9→N"""
    return str(value).translate(_BLACKSTONE_TABLE)

def _encode_price(value):
    """MYKOTHARIZ cipher: 0→Z 1→M 2→Y 3→K 4→O 5→T 6→H 7→A 8→R 9→I"""
    return str(value).translate(_MYKOTHARIZ_TABLE)


class JewelryMCode(models.Model):
    _name = 'jewelry.mcode'
    _description = 'Manufacturer Code'
    
    name = fields.Char(string='M. Code', required=True, size=3)
    partner_id = fields.Many2one('res.partner', string='Vendor / Manufacturer') # Optional: link to actual vendor
    
    _sql_constraints = [('name_uniq', 'unique(name)', 'This Manufacturer Code already exists!')]

class JewelrySize(models.Model):
    _name = 'jewelry.size'
    _description = 'Jewelry Size'
    _order = 'name'
    
    name = fields.Char(string='Size Name', required=True)

class JewelryLessType(models.Model):
    _name = 'jewelry.less.type'
    _description = 'Less Deduction Type'
    
    name = fields.Char(string='Type Name', required=True)

class JewelryBarcodeItem(models.Model):
    _name = 'jewelry.barcode.item'
    _description = 'Barcode Tagged Jewelry Item'
    _rec_name = 'barcode' # Makes the Barcode the default display name across Odoo

    # Enforce strict database uniqueness for the Barcode
    _sql_constraints = [
        ('barcode_uniq', 'unique(barcode)', 'This Barcode ID already exists! Each tag must be unique.')
    ]

    # --- Core Identifiers ---
    barcode = fields.Char(string='Barcode ID', required=True, copy=False, readonly=False, index=True, default=lambda self: 'New')
    name = fields.Char(string='Item Name', required=True)
    m_code = fields.Many2one('jewelry.mcode', string='M. Code (Manufacturer)')
    size = fields.Many2one('jewelry.size', string='Size')
    
    image_1920 = fields.Image(string='Design Photo', max_width=1920, max_height=1920)

    # --- Specifications ---
    
    pieces = fields.Integer(string='Pieces', default=1, help='Number of pieces that make up this specific item.')
    narration = fields.Text(string='Narration')

    # --- Consumption baseline -------------------------------------------------
    # A tag is one physical lot. When part of it is sold (or handed out on
    # approval) the less/charge lines must shrink by the pieces ratio. Scaling
    # the *current* values repeatedly is not reversible (once the tag hits 0
    # pieces the ratio is 0/0), so the very first time a tag is consumed we
    # freeze its original figures and always re-derive the children as
    # `original x pieces / orig_pieces`. Snapshotting lazily means existing
    # tags need no data migration.
    orig_pieces = fields.Integer(string='Original Pieces', readonly=True, copy=False)
    orig_weight = fields.Float(
        string='Original Gross Weight', digits=(16, 3), readonly=True, copy=False,
        help='Gross weight of the whole lot before anything was taken off it. '
             'Only used to suggest a per-piece weight — pieces are rarely equal, '
             'so the weighed value always wins.',
    )
    baseline_set = fields.Boolean(string='Baseline Frozen', readonly=True, copy=False)

    # --- Weights & Calculations ---
    weight = fields.Float(string='Gross Weight', digits=(16, 3), required=True, default=0.0)

    less_ids = fields.One2many('jewelry.item.less', 'item_id', string='Less (Deductions)')

    total_less = fields.Float(
        string='Total Less Weight',
        compute='_compute_weights',
        store=True,
        readonly=True,
        digits=(16, 3)
    )

    net_weight = fields.Float(
        string='Net Weight',
        compute='_compute_weights',  # Updated to the combined method
        store=True,
        readonly=True,
        digits=(16, 3)
    )

    total_charges = fields.Float(
        string='Total Charges',
        compute='_compute_total_charges',
        store=True,
        readonly=True,
        digits=(16, 2)
    )

    less_deduction_pct = fields.Float(
        string='Less Deduction %',
        digits=(5, 2),
        default=0.0,
        help='Percentage to deduct from less weight when printing the tag (0 = no deduction).'
    )
    charge_deduction_pct = fields.Float(
        string='Charge Deduction %',
        digits=(5, 2),
        default=0.0,
        help='Percentage to deduct from charges when printing the tag. Auto-fills from Less Deduction % but can be changed independently.'
    )

    @api.onchange('less_deduction_pct')
    def _onchange_less_deduction_pct(self):
        self.charge_deduction_pct = self.less_deduction_pct

    # --- Item code derivation ------------------------------------------------
    @api.depends('category.code', 'subcategory.code')
    def _compute_item_code(self):
        for item in self:
            parts = [p for p in (item.category.code, item.subcategory.code) if p]
            item.item_code = '-'.join(parts) if parts else False

    @api.onchange('category')
    def _onchange_category(self):
        # Drop a sub-category that no longer belongs to the chosen category so
        # the pair shown on screen is always consistent.
        if self.subcategory and self.subcategory.category_id != self.category:
            self.subcategory = False

    # --- Item Details ---
    # item_code is no longer picked by hand: it is derived from the category
    # and sub-category codes as "<category.code>-<subcategory.code>".
    item_code   = fields.Char(
        string='Item Code',
        compute='_compute_item_code',
        store=True,
        index=True,
        readonly=True,
        help='Built automatically from the category and sub-category codes.',
    )
    purity      = fields.Many2one('jewelry.purity', string='Purity')
    category    = fields.Many2one('jewelry.category', string='Category')
    subcategory = fields.Many2one(
        'jewelry.subcategory', string='Sub-Category',
        domain="[('category_id', '=', category)]",
    )
    make        = fields.Many2one('jewelry.make', string='Make')
    active      = fields.Boolean(default=True, string='Active')
    min_price   = fields.Float(string='Min Selling Price', digits=(16, 2))
    max_price   = fields.Float(string='Max Selling Price', digits=(16, 2))
    barcode_qr_data = fields.Char(string='QR Data URI', compute='_compute_barcode_qr')

    # --- Financial & Categorization ---
    charge_ids = fields.One2many('jewelry.item.charge', 'item_id', string='Charges')
    design_tag_ids = fields.Many2many('jewelry.design.tag', string='Design Tags')

    @api.model_create_multi
    def create(self, vals_list):
        # A safe alphabet excluding visually similar characters (O, 0, I, 1, L)
        safe_alphabet = "qwertyuiopasdfghjklzxcvbnmABCDEFGHJKMNPQRSTOILUVWXYZ1234567890"
        
        for vals in vals_list:
            if vals.get('barcode', 'New') == 'New':
                # The Collision-Proof Loop
                while True:
                    # Generate a random 6-character string
                    proposed_barcode = ''.join(random.choices(safe_alphabet, k=6))
                    
                    # Search the database to see if this string already exists
                    existing = self.search([('barcode', '=', proposed_barcode)], limit=1)
                    
                    # If the search returns nothing, the barcode is unique!
                    if not existing:
                        vals['barcode'] = proposed_barcode
                        break  # Exit the while loop and proceed with creation
                        
        return super(JewelryBarcodeItem, self).create(vals_list)

    # ── Tag helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _encode_tag_pct(less_wt, gross_wt):
        """Return BLACKSTONE-encoded less percentage string."""
        if not gross_wt:
            return ''
        pct = round(less_wt / gross_wt * 100)
        return _encode_digits(str(pct))

    @staticmethod
    def _encode_tag_wt(wt):
        """Return BLACKSTONE-encoded weight string (3 decimal places)."""
        return _encode_digits(f'{wt:.3f}')

    @staticmethod
    def _encode_tag_price(price):
        """Return MYKOTHARIZ-encoded price string (whole rupees, no decimals)."""
        return _encode_price(f'{price:.0f}')

    def _tag_date_str(self):
        """Return date formatted as dd/mmyy (e.g. 16/626 for 16-Jun-2026)."""
        from datetime import date
        today = date.today()
        return f'{today.day}/{today.month}{str(today.year)[2:]}'

    def action_print_tag(self):
        report = self.env.ref('custom_stock_barcode.action_report_jewelry_tag')

        report_url = f'/report/pdf/{report.report_name}/{self.id}?time={fields.Datetime.now().timestamp()}'

        # 3. Return a URL action to force a new tab
        return {
            'type': 'ir.actions.act_url',
            'url': report_url,
            'target': 'new',  # 'new' tells Odoo to open a new browser tab
        }

    @api.depends('barcode')
    def _compute_barcode_qr(self):
        try:
            import qrcode
        except ImportError:
            for rec in self:
                rec.barcode_qr_data = ''
            return
        for rec in self:
            if not rec.barcode or rec.barcode == 'New':
                rec.barcode_qr_data = ''
                continue
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=1,
            )
            qr.add_data(rec.barcode)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            rec.barcode_qr_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()

    # ── Weight computation ────────────────────────────────────────────────────

    @api.depends('weight', 'less_ids.weight')
    def _compute_weights(self):
        for item in self:
            # Calculate the sum once
            calculated_total_less = sum(less_line.weight for less_line in item.less_ids)
            
            # Assign to both fields using float_round for precision
            item.total_less = float_round(calculated_total_less, precision_digits=3)
            item.net_weight = float_round(item.weight - calculated_total_less, precision_digits=3)


    @api.depends('charge_ids.amount')
    def _compute_total_charges(self):
        for item in self:
            item.total_charges = float_round(
                sum(charge.amount for charge in item.charge_ids),
                precision_digits=2
            )

    # ── Consumption engine ────────────────────────────────────────────────────
    # Shared by scan-to-bill / tag splitting (custom_jewellery_billing) and by
    # the approval memos below. Everything that removes stock from a tag goes
    # through _apply_consumption so splits, edits and returns stay exact.

    @api.model
    def _find_by_barcode(self, code):
        """Look a tag up by the string its QR encodes. Archived (fully sold)
        tags are included so the caller can say 'out of stock' rather than
        'unknown barcode'."""
        if not code:
            return self.browse()
        return self.with_context(active_test=False).search(
            [('barcode', '=', code.strip())], limit=1,
        )

    def _ensure_consumption_baseline(self):
        """Freeze the original pieces / less / charges the first time a tag is
        touched. Idempotent."""
        for tag in self.sudo():
            if tag.baseline_set:
                continue
            tag.write({
                'orig_pieces': tag.pieces or 1,
                'orig_weight': tag.weight,
                'baseline_set': True,
            })
            for less in tag.less_ids:
                less.write({'orig_weight': less.weight})
            for charge in tag.charge_ids:
                charge.write({'orig_amount': charge.amount})

    def _per_piece_rates(self):
        """Return (less_per_piece, charges_per_piece) off the frozen baseline.
        Read-only: safe to call from an onchange, and falls back to the current
        figures for a tag that has never been consumed."""
        self.ensure_one()
        if self.baseline_set and self.orig_pieces:
            base_pieces = self.orig_pieces
            total_less = sum(line.orig_weight for line in self.less_ids)
            total_charges = sum(charge.orig_amount for charge in self.charge_ids)
        else:
            base_pieces = self.pieces or 1
            total_less = sum(line.weight for line in self.less_ids)
            total_charges = sum(charge.amount for charge in self.charge_ids)
        return total_less / base_pieces, total_charges / base_pieces

    def _per_piece_weight(self):
        """Suggested gross weight of one piece, off the frozen baseline so it
        stays meaningful after the tag has been partly consumed.

        Pieces of a lot are rarely equal, so this is only ever a starting
        figure: whoever takes the goods weighs them and overwrites it.
        """
        self.ensure_one()
        # orig_weight is 0 on tags whose baseline was frozen before this field
        # existed; fall back to what is left on the tag rather than suggest 0 g.
        if self.baseline_set and self.orig_pieces and self.orig_weight:
            return self.orig_weight / self.orig_pieces
        return (self.weight / self.pieces) if self.pieces else 0.0

    def _apply_consumption(self, d_pieces, d_weight):
        """Take `d_pieces` pieces and `d_weight` grams off this tag; negative
        values put them back. Less/charge lines are always re-derived from the
        frozen baseline, so any sequence of splits and reversals — including a
        restore from zero pieces — lands on the exact original figures. A tag
        that reaches 0 pieces is archived."""
        self.ensure_one()
        if not d_pieces and not d_weight:
            return
        tag = self.sudo()
        tag._ensure_consumption_baseline()

        new_pieces = tag.pieces - d_pieces
        if new_pieces < 0:
            raise UserError(
                f'Tag {tag.barcode} ({tag.name}) only has {tag.pieces} piece(s) left; '
                f'cannot take {d_pieces}.'
            )
        new_weight = float_round(tag.weight - d_weight, precision_digits=3)
        if float_compare(new_weight, 0.0, precision_digits=3) < 0:
            raise UserError(
                f'Tag {tag.barcode} ({tag.name}) only has {tag.weight:.3f} g left; '
                f'cannot take {d_weight:.3f} g.'
            )

        # Leaving pieces behind with no weight means the cashier took the whole
        # lot's weight for a partial sale — almost always a forgotten weighing.
        if (new_pieces > 0
                and float_compare(tag.weight, 0.0, precision_digits=3) > 0
                and float_compare(new_weight, 0.0, precision_digits=3) == 0):
            raise UserError(
                f'Tag {tag.barcode} ({tag.name}) would keep {new_pieces} piece(s) with no '
                f'weight left. Enter the weighed gross weight of the pieces being taken.'
            )

        ratio = (new_pieces / tag.orig_pieces) if tag.orig_pieces else 0.0
        old_ratio = (tag.pieces / tag.orig_pieces) if tag.orig_pieces else 0.0

        tag.write({'pieces': new_pieces, 'weight': new_weight})

        for less in tag.less_ids:
            # A deduction line added after the baseline was frozen has no
            # original of its own — back-derive one from where it stands now.
            if not less.orig_weight and less.weight and old_ratio:
                less.write({'orig_weight': float_round(less.weight / old_ratio, precision_digits=3)})
            less.write({'weight': float_round(less.orig_weight * ratio, precision_digits=3)})
        for charge in tag.charge_ids:
            if not charge.orig_amount and charge.amount and old_ratio:
                charge.write({'orig_amount': float_round(charge.amount / old_ratio, precision_digits=2)})
            charge.write({'amount': float_round(charge.orig_amount * ratio, precision_digits=2)})

        # Archive last so the child writes above are not done on an inactive
        # record; un-archive automatically when stock comes back.
        if bool(new_pieces) != tag.active:
            tag.write({'active': bool(new_pieces)})

    def _prepare_bill_line_vals(self):
        """Values for a custom.bill.line covering this whole tag. The cashier
        then lowers `pieces_taken` and types the weighed gross for a split."""
        self.ensure_one()
        return {
            'name': f'{self.name} [{self.barcode}]',
            'source_item_id': self.id,
            'pieces_taken': self.pieces,
            'weight': self.weight,
            'less': float_round(sum(line.weight for line in self.less_ids), precision_digits=3),
            'charges': self.total_charges,
            'touch': (self.purity.value / 100.0) if self.purity else 0.0,
        }

    def _prepare_approval_line_vals(self):
        """Values for a jewelry.approval.line covering this whole tag."""
        self.ensure_one()
        return {
            'source_item_id': self.id,
            'pieces_taken': self.pieces,
            'weight': self.weight,
            'less': float_round(sum(line.weight for line in self.less_ids), precision_digits=3),
            'charges': self.total_charges,
        }


# --- RELATIONAL SUB-MODELS ---

class JewelryItemLess(models.Model):
    _name = 'jewelry.item.less'
    _description = 'Item Weight Deductions'

    item_id = fields.Many2one('jewelry.barcode.item', string='Item', required=True, ondelete='cascade')
    
    less_type = fields.Many2one('jewelry.less.type', string='Type', required=True)
    
    name = fields.Char(string='Description (Optional)')
    weight = fields.Float(string='Less Weight', digits=(16, 3), required=True)
    # Frozen full-lot weight; see JewelryBarcodeItem._ensure_consumption_baseline.
    orig_weight = fields.Float(string='Original Less Weight', digits=(16, 3), readonly=True, copy=False)


class JewelryItemCharge(models.Model):
    _name = 'jewelry.item.charge'
    _description = 'Item Charges'

    item_id = fields.Many2one('jewelry.barcode.item', string='Item', required=True, ondelete='cascade')
    name = fields.Char(string='Charge Name (e.g., Making, Hallmarking)', required=True)
    amount = fields.Float(string='Amount', required=True, digits=(16, 2))
    # Frozen full-lot amount; see JewelryBarcodeItem._ensure_consumption_baseline.
    orig_amount = fields.Float(string='Original Amount', digits=(16, 2), readonly=True, copy=False)


class JewelryDesignTag(models.Model):
    _name = 'jewelry.design.tag'
    _description = 'Design Tag'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Tag name must be unique!')
    ]


# --- ITEM DETAIL CONFIGURATION MODELS ---

class JewelryPurity(models.Model):
    _name = 'jewelry.purity'
    _description = 'Purity'
    _order = 'value desc'

    name  = fields.Char(string='Label', required=True)
    value = fields.Integer(string='Purity Value', required=True, help='e.g. 9166 for 22K')
    karat = fields.Integer(string='Karat', required=True, help='e.g. 22')

    _sql_constraints = [('value_uniq', 'unique(value)', 'This purity value already exists!')]


class JewelryCategory(models.Model):
    _name = 'jewelry.category'
    _description = 'Jewelry Category'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(
        string='Category Code', required=True, size=3,
        help='Short code (max 3 letters) used to build the item code, e.g. "RG" for Rings.',
    )
    subcategory_ids = fields.One2many(
        'jewelry.subcategory', 'category_id', string='Sub-Categories',
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Category already exists!'),
        ('code_uniq', 'unique(code)', 'Category code must be unique!'),
    ]


class JewelrySubcategory(models.Model):
    _name = 'jewelry.subcategory'
    _description = 'Jewelry Sub-Category'
    _order = 'category_id, name'

    name = fields.Char(required=True)
    code = fields.Char(
        string='Sub-Category Code', required=True, size=3,
        help='Short code (max 3 letters) used to build the item code, e.g. "ST" for Studs.',
    )
    category_id = fields.Many2one(
        'jewelry.category', string='Category', required=True, ondelete='cascade',
    )

    _sql_constraints = [
        ('name_category_uniq', 'unique(name, category_id)',
         'This sub-category already exists under the selected category!'),
    ]


class JewelryMake(models.Model):
    _name = 'jewelry.make'
    _description = 'Jewelry Make'
    _order = 'name'

    name = fields.Char(required=True)

    _sql_constraints = [('name_uniq', 'unique(name)', 'Make already exists!')]