import base64
import io
import random
from odoo import models, fields, api
from odoo.tools.float_utils import float_round

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
    barcode = fields.Char(string='Barcode ID', required=True, copy=False, readonly=True, index=True, default=lambda self: 'New')
    name = fields.Char(string='Item Name', required=True)
    m_code = fields.Many2one('jewelry.mcode', string='M. Code (Manufacturer)')
    size = fields.Many2one('jewelry.size', string='Size')
    
    image_1920 = fields.Image(string='Design Photo', max_width=1920, max_height=1920)

    # --- Specifications ---
    
    pieces = fields.Integer(string='Pieces', default=1, help='Number of pieces that make up this specific item.')
    narration = fields.Text(string='Narration')

    # --- Weights & Calculations ---
    weight = fields.Float(string='Gross Weight', digits=(16, 3), required=True, default=0.0)

    less_ids = fields.One2many('jewelry.item.less', 'item_id', string='Less (Deductions)')

    net_weight = fields.Float(
        string='Net Weight',
        compute='_compute_net_weight',
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
    def _compute_net_weight(self):
        for item in self:
            total_less = sum(less_line.weight for less_line in item.less_ids)
            # Using float_round to prevent floating point microscopic errors
            item.net_weight = float_round(item.weight - total_less, precision_digits=3)

    @api.depends('charge_ids.amount')
    def _compute_total_charges(self):
        for item in self:
            item.total_charges = float_round(
                sum(charge.amount for charge in item.charge_ids),
                precision_digits=2
            )


# --- RELATIONAL SUB-MODELS ---

class JewelryItemLess(models.Model):
    _name = 'jewelry.item.less'
    _description = 'Item Weight Deductions'

    item_id = fields.Many2one('jewelry.barcode.item', string='Item', required=True, ondelete='cascade')
    
    less_type = fields.Many2one('jewelry.less.type', string='Type', required=True)
    
    name = fields.Char(string='Description (Optional)')
    weight = fields.Float(string='Less Weight', digits=(16, 3), required=True)


class JewelryItemCharge(models.Model):
    _name = 'jewelry.item.charge'
    _description = 'Item Charges'

    item_id = fields.Many2one('jewelry.barcode.item', string='Item', required=True, ondelete='cascade')
    name = fields.Char(string='Charge Name (e.g., Making, Hallmarking)', required=True)
    amount = fields.Float(string='Amount', required=True, digits=(16, 2))


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