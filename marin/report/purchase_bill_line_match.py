# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import SQL
from odoo.exceptions import UserError


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
