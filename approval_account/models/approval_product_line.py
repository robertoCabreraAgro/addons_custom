from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools.translate import _


class ApprovalProductLine(models.Model):
    _inherit = "approval.product.line"

    account_move_id = fields.Many2one(
        comodel_name="account.move",
    )

    def _prepare_account_move_values_from_approval(self):
        """Get some values used to create a journal_entryr.
        Called in approval.request `action_create_account_move`.

        :param vendor: a res.partner record
        :return: dict of values"""
        self.ensure_one()
        line_vals = {
            "quantity": 1.0,
        }
        vals = {
            "company_id": self.company_id.id,
            "partner_id": self.approval_request_id.partner_id.id,
            "invoice_payment_term_id": self.approval_request_id.partner_id.property_supplier_payment_term_id.id,
            "move_type": self.approval_request_id.approval_type,
            "line_ids": [
                Command.create(
                    {
                        "product_id": self.product_id.id,
                        "product_uom_id": self.product_uom_id.id,
                        "quantity": self.quantity,
                    },
                )
            ]
        }
        return vals
