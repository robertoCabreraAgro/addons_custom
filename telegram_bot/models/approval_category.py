from odoo import fields, models

from odoo.addons.base_approval.models.approval_category import CATEGORY_SELECTION


class ApprovalCategory(models.Model):
    _inherit = "approval.category"

    has_bsl = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Bank Statement Line",
        help="Specify if a bank statement line must be selected for this type of approval.",
        required=True,
        default="no",
    )
    has_operation_type = fields.Selection(
        selection=CATEGORY_SELECTION,
        help="Specify if an accounting operation type must be selected for this approval.",
        required=True,
        default="no",
    )
