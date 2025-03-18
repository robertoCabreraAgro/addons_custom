from odoo import api, fields, models

from odoo.addons.base_approval.models.approval_category import CATEGORY_SELECTION


class ApprovalCategory(models.Model):
    _inherit = "approval.category"

    # Inherited fields
    approval_type = fields.Selection(
        selection_add=[
            ("fleet_vehicle_log", "Create fleet log"),
            ("entry", "Create Journal Entry"),
            ("in_invoice", "Create Vendor Bill"),
            ("in_refund", "Create Vendor Refund"),
            ("out_invoice", "Create Customer Invoice"),
            ("out_refund", "Create Customer Refund"),
            ("purchase", "Create RFQ's"),
        ],
    )

    # New fields
    has_vehicle = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Vehicle",
        required=True,
        default="no",
    )
    has_odometer = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Odometer",
        required=True,
        default="no",
    )

    @api.onchange("approval_type")
    def _onchange_approval_type(self):
        if self.approval_type == "purchase":
            self.has_product = "required"
            self.has_quantity = "required"
        elif self.approval_type in (
            "in_invoice",
            "in_refund",
            "out_invoice",
            "out_refund",
        ):
            self.has_product = "required"
            self.has_quantity = "required"
        elif self.approval_type == "entry":
            self.has_amount = "required"
        elif self.approval_type == "fleet_vehicle_log":
            self.has_date = "required"
            self.has_vehicle = "required"
            self.has_odometer = "required"
