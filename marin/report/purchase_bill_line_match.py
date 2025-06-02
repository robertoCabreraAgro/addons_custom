from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import SQL


class PurchaseBillLineMatch(models.Model):
    _inherit = "purchase.bill.line.match"

    def action_match_lines(self):
        if len(self.aml_id.move_id) == 1 and self.aml_id.move_id.hide_purchase_matching:
            raise UserError(
                _(
                    "Purchase matching is disabled for this invoice. Please check the following:\n\n"
                    "- All invoice lines might already be linked to purchase orders.\n"
                    "- Invoice lines may not contain any products that can be matched."
                )
            )
        return super().action_match_lines()

    def action_mark_ignore_purchase_bill_matching(self):
        if not self or not self.aml_id:
            raise UserError(_("Select Vendor Bill lines only"))

        self.aml_id.move_id.x_ignore_purchase_bill_matching = True

    def _where_aml(self):
        return SQL(
            """
            %s
            AND aml.product_id IS NOT NULL
            AND NOT am.x_ignore_purchase_bill_matching
            """,
            super()._where_aml()
        )
