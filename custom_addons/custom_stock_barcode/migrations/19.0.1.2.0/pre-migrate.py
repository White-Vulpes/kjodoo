def migrate(cr, version):
    """item_code changed from a Many2one (integer FK to jewelry_item_code) into
    a computed Char. PostgreSQL cannot alter the column type in place while the
    old foreign key still references it, so drop the constraint and the column
    here. Odoo then recreates item_code as the new stored/computed text column
    and recomputes it for every existing item from its category/sub-category
    codes."""
    cr.execute(
        "ALTER TABLE jewelry_barcode_item "
        "DROP CONSTRAINT IF EXISTS jewelry_barcode_item_item_code_fkey"
    )
    cr.execute(
        "ALTER TABLE jewelry_barcode_item DROP COLUMN IF EXISTS item_code"
    )
