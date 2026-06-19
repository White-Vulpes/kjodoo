import random
from odoo import models, fields, api
from odoo.tools.float_utils import float_round

_BLACKSTONE_TABLE = str.maketrans('0123456789', 'EBLACKSTON')

def _encode_digits(value):
    """BLACKSTONE cipher: replace each digit with its letter (0→E, 1→B, 2→L, 3→A, 4→C, 5→K, 6→S, 7→T, 8→O, 9→N)."""
    return str(value).translate(_BLACKSTONE_TABLE)


class JewelryMCode(models.Model):
    _name = 'jewelry.mcode'
    _description = 'Manufacturer Code'
    
    name = fields.Char(string='M. Code', required=True)
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

    # --- Item Details ---
    item_code   = fields.Char(string='Item Code', index=True)
    purity      = fields.Integer(string='Purity', help='e.g. 9999=24K, 9166=22K, 8333=20K, 7500=18K')
    category    = fields.Char(string='Category')
    subcategory = fields.Char(string='Sub-Category')
    make        = fields.Char(string='Make')
    active      = fields.Boolean(default=True, string='Active')

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
        """Return BLACKSTONE-encoded weight string (decimal point preserved)."""
        return _encode_digits(f'{wt:.3f}')

    @staticmethod
    def _purity_to_karat(purity):
        """Convert purity integer (e.g. 9166) to karat label (e.g. 22)."""
        mapping = {9999: 24, 9166: 22, 8750: 21, 8333: 20, 7500: 18, 5833: 14}
        if purity in mapping:
            return mapping[purity]
        return purity // 100 if purity else ''

    def _tag_date_str(self):
        """Return date formatted as dd/mmyy (e.g. 16/626 for 16-Jun-2026)."""
        from datetime import date
        today = date.today()
        return f'{today.day}/{today.month}{str(today.year)[2:]}'

    # ── Weight computation ────────────────────────────────────────────────────

    @api.depends('weight', 'less_ids.weight')
    def _compute_net_weight(self):
        for item in self:
            total_less = sum(less_line.weight for less_line in item.less_ids)
            # Using float_round to prevent floating point microscopic errors
            item.net_weight = float_round(item.weight - total_less, precision_digits=3)


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