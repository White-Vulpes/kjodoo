from odoo import models, fields

class RoughBillImportWizard(models.TransientModel):
    _name = 'custom.rough.bill.import.wizard'
    _description = 'Import Rough Bill as Bill'

    rough_bill_id = fields.Many2one('custom.rough.bill2', string='Rough Bill', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)

    def action_import(self):
        rough = self.rough_bill_id
        new_bill = self.env['custom.bill2'].create({
            'partner_id': self.partner_id.id,
            'date': rough.date,
            'remarks': rough.remarks,
            'show_transaction': rough.show_transaction,
            'karat_24': rough.karat_24,
            'karat_22': rough.karat_22,
            'karat_18': rough.karat_18,
        })

        for line in rough.item_ids:
            self.env['custom.bill2.line'].create({
                'bill_id': new_bill.id,
                'name': line.name,
                'weight': line.weight,
                'less': line.less,
                'melting': line.melting,
                'touch': line.touch,
                'VAT': line.VAT,
                'type': line.type,
                'charges': line.charges,
            })

        for txn in rough.transaction_ids:
            self.env['custom.bill2.transaction'].create({
                'bill_id': new_bill.id,
                'date': txn.date,
                'ttype': txn.ttype,
                'gross_weight': txn.gross_weight,
                'less': txn.less,
                'purity': txn.purity,
                'pure_weight': txn.pure_weight,
                'rate': txn.rate,
                'amount': txn.amount,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Jewelry Bill',
            'res_model': 'custom.bill2',
            'res_id': new_bill.id,
            'view_mode': 'form',
            'target': 'current',
        }
