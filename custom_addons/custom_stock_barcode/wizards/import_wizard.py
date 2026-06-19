import base64
from odoo import models, fields, api
from odoo.exceptions import UserError
from ..models.models import _encode_digits


class JewelryImportWizard(models.TransientModel):
    _name = 'jewelry.import.wizard'
    _description = 'Import Jewelry Items from Excel'

    file_data = fields.Binary(string='Excel File (.xls)', required=True)
    file_name = fields.Char(string='File Name')
    less_type_id = fields.Many2one('jewelry.less.type', string='Default Less Type', required=True)
    rate_per_gram = fields.Float(string='Gold Rate (per gram)', digits=(16, 2),
                                 help='Optional: used to display monetary amount in encoded narration.')

    def action_import(self):
        try:
            import xlrd
        except ImportError:
            raise UserError("The 'xlrd' Python library is required for XLS import. Run: pip install xlrd")

        raw = base64.b64decode(self.file_data)
        try:
            wb = xlrd.open_workbook(file_contents=raw)
        except Exception as e:
            raise UserError(f"Could not open Excel file: {e}")

        sh = wb.sheets()[0]
        if sh.nrows < 2:
            raise UserError("The Excel file has no data rows.")

        headers = [str(sh.cell_value(0, c)).strip() for c in range(sh.ncols)]

        def col(row_data, name):
            try:
                idx = headers.index(name)
                val = row_data[idx]
                return val if val != '' else None
            except ValueError:
                return None

        created_ids = []
        ItemModel = self.env['jewelry.barcode.item']

        for r in range(1, sh.nrows):
            row = [sh.cell_value(r, c) for c in range(sh.ncols)]

            item_code   = str(col(row, 'Item Code') or '').strip()
            brand_name  = str(col(row, 'Brand Name') or '').strip()
            brand_code  = str(col(row, 'Brand Code') or '').strip()
            subcategory = str(col(row, 'Subcategory') or '').strip()
            category    = str(col(row, 'Category') or '').strip()
            make        = str(col(row, 'Make') or '').strip()
            status      = str(col(row, 'Status') or 'Active').strip()
            size_name   = str(col(row, 'Size') or '').strip()
            pcs_raw     = col(row, 'Piece Name')
            gross_raw   = col(row, 'Gross Weight')
            less_raw    = col(row, 'Less Weight')
            purity_raw  = col(row, 'Purity')

            gross_weight = float(gross_raw) if gross_raw not in (None, '') else 0.0
            less_weight  = float(less_raw)  if less_raw  not in (None, '') else 0.0
            pieces       = int(float(pcs_raw)) if pcs_raw not in (None, '') else 1
            purity       = int(float(purity_raw)) if purity_raw not in (None, '') else 0

            # Item name: Brand Name – Sub-Category
            name_parts = [p for p in [brand_name, subcategory] if p]
            item_name = ' - '.join(name_parts) if name_parts else (item_code or 'Unnamed')

            # get-or-create size
            size_id = False
            if size_name:
                size_rec = self.env['jewelry.size'].search([('name', '=', size_name)], limit=1)
                if not size_rec:
                    size_rec = self.env['jewelry.size'].create({'name': size_name})
                size_id = size_rec.id

            # get-or-create mcode
            mcode_id = False
            if brand_code:
                mcode_rec = self.env['jewelry.mcode'].search([('name', '=', brand_code)], limit=1)
                if not mcode_rec:
                    mcode_rec = self.env['jewelry.mcode'].create({'name': brand_code})
                mcode_id = mcode_rec.id

            # Build encoded narration
            narration = self._build_narration(
                less_weight, gross_weight, self.less_type_id, self.rate_per_gram
            )

            vals = {
                'item_code':   item_code,
                'name':        item_name,
                'm_code':      mcode_id,
                'size':        size_id,
                'pieces':      pieces,
                'weight':      gross_weight,
                'purity':      purity,
                'category':    category,
                'subcategory': subcategory,
                'make':        make,
                'active':      status.lower() == 'active',
                'narration':   narration,
                'less_ids': [(0, 0, {
                    'less_type': self.less_type_id.id,
                    'weight': less_weight,
                })] if less_weight else [],
            }

            item = ItemModel.create(vals)
            created_ids.append(item.id)

        return {
            'type': 'ir.actions.act_window',
            'name': f'Imported Items ({len(created_ids)})',
            'res_model': 'jewelry.barcode.item',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_ids)],
            'target': 'current',
        }

    @staticmethod
    def _build_narration(less_weight, gross_weight, less_type, rate_per_gram=0.0):
        """Return encoded narration string using BLACKSTONE cipher."""
        if not gross_weight:
            return ''
        pct = round(less_weight / gross_weight * 100)
        type_code = (less_type.name[:3].upper() if less_type else 'UNK')
        enc_pct = _encode_digits(str(pct))
        enc_wt  = _encode_digits(f'{less_weight:.3f}')
        narration = f'{type_code}-{enc_pct}%WT{enc_wt}'
        if rate_per_gram:
            enc_rate = _encode_digits(str(int(rate_per_gram)))
            narration += f'R{enc_rate}'
        return narration
