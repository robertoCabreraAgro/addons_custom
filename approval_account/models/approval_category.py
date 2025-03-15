from odoo import api, fields, models


class ApprovalCategory(models.Model):
    _inherit = "approval.category"

    approval_type = fields.Selection(
        selection_add=[
            ("entry", "Create Journal Entry"),
            ("in_invoice", "Create Vendor Bill"),
            ("in_refund", "Create Vendor Refund"),
            ("out_invoice", "Create Customer Invoice"),
            ("out_refund", "Create Customer Refund"),
        ],
    )

    @api.onchange("approval_type")
    def _onchange_approval_type(self):
        if self.approval_type in (
            "in_invoice",
            "in_refund",
            "out_invoice",
            "out_refund",
        ):
            self.has_product = "required"
            self.has_quantity = "required"
        elif self.approval_type == "entry":
            self.has_amount = "required"
        else:
            super()._onchange_approval_type()
