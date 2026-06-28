from odoo import models, fields, api

class GramTag(models.Model):
    _name = 'gram.tag'
    _description = 'RTGS Status Tags'
    _order = 'sequence, id'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index')
    sequence = fields.Integer(default=10, string='Sequence')

class GramRecord(models.Model):
    _name = 'gram.record'
    _description = 'RTGS Entry Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Reference', required=True, default='New', copy=False)
    partner_id = fields.Many2one(comodel_name="res.partner", string="")
    phone = fields.Char(string='Phone', related='partner_id.phone', store=True, readonly=False)

    grams = fields.Float(string='Grams', digits=(16, 3))
    rate = fields.Float(string='Rate', digits=(16, 2))
    pure = fields.Float(string='Pure', digits=(16, 3))
    amount = fields.Float(string='Amount', digits=(16, 2))
    touch = fields.Float(string='Touch', digits=(16, 2), store=True, default=95)
    bill_flag = fields.Boolean(string='Generate Bill', default=False)

    gst = fields.Char(string='Rate w/o GST', compute='_compute_gst', store=True)
    pure_calc = fields.Char(string='Pure Calculation', compute='_compute_pure_calc', store=True)

    @api.depends('amount', 'pure')
    def _compute_pure_calc(self):
        for record in self:
            pure_rate = record.amount / record.pure if record.pure > 0 else 0
            record.pure_calc = f"{record.pure:.3f} *{pure_rate:.2f} = {record.amount:.2f}"

    @api.depends('rate', 'grams', 'amount')
    def _compute_gst(self):
        for record in self:
            amountWithoutGST = record.amount / 1.03
            rateWithoutGST = amountWithoutGST / record.grams if record.grams > 0 else 0
            record.gst = f"{record.grams} * {rateWithoutGST:.2f} = {amountWithoutGST:.2f} + 3% GST = {record.amount}"

    # Completed Tags
    tag_ids = fields.Many2many(
        'gram.tag', 
        relation='gram_record_completed_tags_rel',
        string='Status',
        tracking=True,
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
        # We inject the context HERE, so only the Kanban column headers get renamed!
        return self.env['gram.tag']

    # --- Calculations ---
    @api.onchange('pure', 'amount')
    def _onchange_pure_rate(self):
        for record in self:
            if record.pure > 0:
                record.rate = (record.amount / record.pure)
            elif record.amount > 0 and record.rate > 0:
                record.pure = record.amount / record.rate
                
    @api.onchange('phone')
    def _onchange_phone(self):
        for record in self:
            if record.partner_id and record.partner_id.phone != record.phone:
                record.partner_id.phone = record.phone

    @api.onchange('rate')
    def _onchange_rate(self):
        for record in self:
            if record.pure > 0:
                record.amount = record.rate * record.pure
            elif record.amount > 0:
                record.pure = record.amount / record.rate
    
    @api.onchange('pure', 'touch')
    def _on_change_pure(self):
        for record in self:
            if record.touch > 0 and record.pure > 0:
                record.grams = record.pure / (record.touch / 100)

    def _notify_thread_by_email(self, message, recipients_data, **kwargs):
        return