from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def action_post(self):
        """Override to add credit validation before posting invoice"""
        for move in self.filtered(lambda m: m.is_sale_document()):
            # Only validate for customer invoices
            move.partner_id._validate_credit_checks(
                payment_term=move.invoice_payment_term_id
            )
        
        # Call the original method
        return super(AccountMove, self).action_post()
