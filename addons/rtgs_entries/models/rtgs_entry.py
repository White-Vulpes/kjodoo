from odoo import models, fields, api

class GramTag(models.Model):
    _name = 'gram.tag'
    _description = 'Gram Record Tags'
    _order = 'sequence, id'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index')
    sequence = fields.Integer(default=10, string='Sequence')


class GramRecord(models.Model):
    _name = 'gram.record'
    _description = 'Gram Record Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Reference', required=True, default='New', copy=False)
    partner_id = fields.Many2one(comodel_name="res.partner", string="")
    
    grams = fields.Float(string='Grams', digits=(16, 3))
    rate = fields.Float(string='Rate', digits=(16, 2))
    amount = fields.Float(string='Amount', digits=(16, 2))

    gst = fields.Char(string='Rate w/o GST', compute='_compute_gst', store=True)

    @api.depends('rate', 'grams', 'amount')
    def _compute_gst(self):
        for record in self:
            amountWithoutGST = record.amount / 1.03
            rateWithoutGST = amountWithoutGST / record.grams
            record.gst = f"{record.grams} * {rateWithoutGST:.2f} = {amountWithoutGST:.2f} + 3% GST = {record.amount}"

    # Completed Tags
    tag_ids = fields.Many2many(
        'gram.tag', 
        relation='gram_record_completed_tags_rel',
        string='Status',
        default=lambda self: self.env['gram.tag'].search([('name', 'in', ['RTGS Recieved', 'Ratecut Done'])]).ids
    )

    # Missing Tags (This drives the Kanban View)
    missing_tag_ids = fields.Many2many(
        'gram.tag', 
        relation='gram_record_missing_tags_rel',
        string='Pending Stages', 
        compute='_compute_missing_tags', 
        store=True, 
        group_expand='_read_group_missing_tags'
    )

    @api.depends('tag_ids')
    def _compute_missing_tags(self):
        # Fetch all available tags in their proper sequence
        all_tags = self.env['gram.tag'].search([], order='sequence asc')
        for record in self:
            # The missing tags are simply ALL tags minus the COMPLETED tags
            record.missing_tag_ids = all_tags - record.tag_ids

    @api.model
    def _read_group_missing_tags(self, tags, domain, order=None, **kwargs):
        # This ensures every tag gets a column in the Kanban, even if empty
        return self.env['gram.tag'].search([], order=order)

    # --- Calculations ---
    @api.onchange('grams', 'rate')
    def _onchange_grams_rate(self):
        for record in self:
            if record.grams and record.rate:
                record.amount = int(record.grams * record.rate)

    @api.onchange('amount')
    def _onchange_amount(self):
        for record in self:
            if record.amount and record.rate and record.rate > 0:
                record.grams = record.amount / record.rate