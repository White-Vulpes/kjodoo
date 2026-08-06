import base64
import io
from odoo import models, fields
from odoo.exceptions import UserError


class JewelryImportWizard(models.TransientModel):
    _name = 'jewelry.import.wizard'
    _description = 'Import Jewelry Items from Excel'

    file_data = fields.Binary(string='Excel File (.xls / .xlsx)', required=True)
    file_name = fields.Char(string='File Name')

    def action_import(self):
        raw = base64.b64decode(self.file_data)
        fname = (self.file_name or '').lower()

        # ── Load workbook ────────────────────────────────────────────────────
        if fname.endswith('.xls') and not fname.endswith('.xlsx'):
            try:
                import xlrd
            except ImportError:
                raise UserError("Install 'xlrd' to read .xls files:  pip install 'xlrd==1.2.0'")
            try:
                wb = xlrd.open_workbook(file_contents=raw)
            except Exception as e:
                raise UserError(f"Cannot open Excel file: {e}")
            sh = wb.sheets()[0]
            if sh.nrows < 2:
                raise UserError("The Excel file has no data rows.")
            headers = [str(sh.cell_value(0, c)).strip() for c in range(sh.ncols)]
            data_rows = [
                [sh.cell_value(r, c) for c in range(sh.ncols)]
                for r in range(1, sh.nrows)
            ]
        else:
            try:
                import openpyxl
            except ImportError:
                raise UserError("Install 'openpyxl' to read .xlsx files:  pip install openpyxl")
            try:
                wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            except Exception as e:
                raise UserError(f"Cannot open Excel file: {e}")
            ws = wb.active
            all_rows = list(ws.iter_rows(values_only=True))
            if len(all_rows) < 2:
                raise UserError("The Excel file has no data rows.")
            headers = [str(c).strip() if c is not None else '' for c in all_rows[0]]
            data_rows = [
                ['' if c is None else c for c in r]
                for r in all_rows[1:]
            ]

        # ── Column helpers ───────────────────────────────────────────────────
        hmap = {h: i for i, h in enumerate(headers) if h}

        def col(row, name, default=None):
            idx = hmap.get(name)
            if idx is None or idx >= len(row):
                return default
            v = row[idx]
            return v if v not in (None, '') else default

        def col_str(row, name):
            v = col(row, name, '')
            return str(v).strip() if v not in (None, '') else ''

        def col_float(row, name, default=0.0):
            v = col(row, name)
            try:
                return float(v) if v not in (None, '') else default
            except (ValueError, TypeError):
                return default

        def col_int(row, name, default=0):
            v = col(row, name)
            try:
                return int(float(v)) if v not in (None, '') else default
            except (ValueError, TypeError):
                return default

        # ── Discover numbered less / charge columns ──────────────────────────
        less_nums = sorted({
            int(h.rsplit(None, 1)[-1])
            for h in headers
            if h.startswith('Less Type ') and h.rsplit(None, 1)[-1].isdigit()
        })
        charge_nums = sorted({
            int(h.rsplit(None, 1)[-1])
            for h in headers
            if h.startswith('Charge Name ') and h.rsplit(None, 1)[-1].isdigit()
        })

        # ── get-or-create helper ─────────────────────────────────────────────
        def get_or_create(model_name, name_val, extra=None):
            if not name_val:
                return False
            rec = self.env[model_name].search([('name', '=', name_val)], limit=1)
            if not rec:
                vals = {'name': name_val}
                if extra:
                    vals.update(extra)
                rec = self.env[model_name].create(vals)
            return rec.id

        def derive_code(name_val):
            """Fallback short code (first 3 alphanumerics, uppercased) used when
            importing categories / sub-categories that have no explicit code."""
            letters = ''.join(ch for ch in (name_val or '') if ch.isalnum()).upper()
            return letters[:3] or 'XXX'

        _karat_map = {9999: 24, 9166: 22, 8750: 21, 8333: 20, 7500: 18, 5833: 14, 5000: 12}
        ItemModel = self.env['jewelry.barcode.item']
        created_ids = []
        errors = []

        for r_idx, row in enumerate(data_rows, start=2):
            if all(v in (None, '', 0) for v in row):
                continue

            gross_weight = col_float(row, 'Gross Weight')
            if not gross_weight:
                errors.append(f"Row {r_idx}: missing Gross Weight — skipped.")
                continue

            # ── Scalar fields ────────────────────────────────────────────────
            barcode_str     = col_str(row, 'Barcode')  # <-- ADDED
            item_code_str   = col_str(row, 'Item Code')
            brand_name      = col_str(row, 'Brand Name')
            brand_code      = col_str(row, 'Brand Code')
            subcategory_str = col_str(row, 'Subcategory')
            category_str    = col_str(row, 'Category')
            make_str        = col_str(row, 'Make')
            size_name       = col_str(row, 'Size')
            status          = col_str(row, 'Status') or 'Active'
            pieces          = col_int(row, 'Piece Name', 1) or col_int(row, 'Pieces', 1) or 1
            purity_int      = col_int(row, 'Purity')
            min_price       = col_float(row, 'Min Price')
            max_price       = col_float(row, 'Max Price')
            narration       = col_str(row, 'Narration')
            less_ded_pct    = col_float(row, 'Less Deduction %')
            charge_ded_pct  = col_float(row, 'Charge Deduction %', default=less_ded_pct)

            # ── get-or-create lookups ────────────────────────────────────────
            size_id        = get_or_create('jewelry.size', size_name)
            mcode_id       = get_or_create('jewelry.mcode', brand_code)
            category_id    = get_or_create(
                'jewelry.category', category_str,
                extra={'code': derive_code(category_str)},
            )
            make_id        = get_or_create('jewelry.make', make_str)

            # Sub-categories now belong to a category and carry their own code.
            # Without a category there is nothing to attach them to, so skip.
            subcategory_id = False
            if subcategory_str and category_id:
                Sub = self.env['jewelry.subcategory']
                sub = Sub.search([
                    ('name', '=', subcategory_str),
                    ('category_id', '=', category_id),
                ], limit=1)
                if not sub:
                    sub = Sub.create({
                        'name': subcategory_str,
                        'code': derive_code(subcategory_str),
                        'category_id': category_id,
                    })
                subcategory_id = sub.id

            purity_id = False
            if purity_int:
                purity_rec = self.env['jewelry.purity'].search([('value', '=', purity_int)], limit=1)
                if not purity_rec:
                    karat = _karat_map.get(purity_int, purity_int // 100)
                    purity_rec = self.env['jewelry.purity'].create({
                        'name': f'{karat}K',
                        'value': purity_int,
                        'karat': karat,
                    })
                purity_id = purity_rec.id

            # ── Less records ─────────────────────────────────────────────────
            less_lines = []
            if less_nums:
                for n in less_nums:
                    lt_name = col_str(row, f'Less Type {n}')
                    lt_wt   = col_float(row, f'Less Weight {n}')
                    if not lt_name or not lt_wt:
                        continue
                    lt_id = get_or_create('jewelry.less.type', lt_name)
                    less_lines.append((0, 0, {'less_type': lt_id, 'weight': lt_wt}))
            else:
                # Fallback: single-column format (Less Type + Less Weight)
                lt_name = col_str(row, 'Less Type')
                lt_wt   = col_float(row, 'Less Weight')
                if lt_name and lt_wt:
                    lt_id = get_or_create('jewelry.less.type', lt_name)
                    less_lines.append((0, 0, {'less_type': lt_id, 'weight': lt_wt}))

            # ── Charge records ───────────────────────────────────────────────
            charge_lines = []
            for n in charge_nums:
                ch_name   = col_str(row, f'Charge Name {n}')
                ch_amount = col_float(row, f'Charge Amount {n}')
                if not ch_name or not ch_amount:
                    continue
                charge_lines.append((0, 0, {'name': ch_name, 'amount': ch_amount}))

            # ── Item name ────────────────────────────────────────────────────
            name_parts = [p for p in [brand_name, subcategory_str] if p]
            item_name = ' - '.join(name_parts) if name_parts else (item_code_str or 'Unnamed')

            # ── Create ───────────────────────────────────────────────────────
            try:
                item = ItemModel.create({
                    'name':                 item_name,
                    'barcode':              barcode_str,  # <-- ADDED
                    'm_code':               mcode_id,
                    'size':                 size_id,
                    'pieces':               pieces,
                    'weight':               gross_weight,
                    'purity':               purity_id,
                    'category':             category_id,
                    'subcategory':          subcategory_id,
                    'make':                 make_id,
                    'active':               status.lower() == 'active',
                    'min_price':            min_price,
                    'max_price':            max_price,
                    'narration':            narration,
                    'less_deduction_pct':   less_ded_pct,
                    'charge_deduction_pct': charge_ded_pct,
                    'less_ids':             less_lines,
                    'charge_ids':           charge_lines,
                })
                created_ids.append(item.id)
            except Exception as e:
                errors.append(f"Row {r_idx}: {e}")

        if errors and not created_ids:
            raise UserError("Import failed — no items created.\n\n" + '\n'.join(errors))

        if errors:
            # Partial success — commit what we have and warn
            self.env['bus.bus']._sendone(
                self.env.user.partner_id,
                'simple_notification',
                {'title': 'Import warnings', 'message': '\n'.join(errors), 'sticky': True},
            )

        return {
            'type': 'ir.actions.act_window',
            'name': f'Imported Items ({len(created_ids)})',
            'res_model': 'jewelry.barcode.item',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_ids)],
            'target': 'current',
        }
