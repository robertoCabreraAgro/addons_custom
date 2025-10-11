from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ApprovalRequestPurchaseApprover(models.Model):
    """Approvers for purchase approval requests."""
    _name = "approval.request.purchase.approver"
    _description = "Purchase Approval Request Approver"
    _order = "sequence, id"
    _rec_name = "user_id"

    # ============================================================================
    # FIELDS
    # ============================================================================

    request_id = fields.Many2one(
        "approval.request.purchase",
        string="Approval Request",
        required=True,
        ondelete="cascade"
    )

    user_id = fields.Many2one(
        "res.users",
        string="Approver",
        required=True,
        domain="[('share', '=', False)]"
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence for sequential approval"
    )

    role = fields.Selection([
        ("approver", "Approver"),
        ("manager", "Manager"),
        ("finance", "Finance"),
        ("purchasing", "Purchasing Manager"),
        ("executive", "Executive")
    ], string="Role", default="approver", required=True)

    status = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("refused", "Refused")
    ], string="Status", default="pending", required=True)

    required = fields.Boolean(
        string="Required",
        default=True,
        help="This approval is mandatory"
    )

    approved_date = fields.Datetime(
        string="Approved Date",
        readonly=True
    )

    comment = fields.Text(
        string="Comment"
    )

    # ============================================================================
    # CONSTRAINTS
    # ============================================================================

    @api.constrains("user_id", "request_id")
    def _check_unique_user_per_request(self):
        for approver in self:
            domain = [
                ("request_id", "=", approver.request_id.id),
                ("user_id", "=", approver.user_id.id),
                ("id", "!=", approver.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(
                    _("User %s is already an approver for this request.") %
                    approver.user_id.name
                )


class ApprovalRequestPurchaseHistory(models.Model):
    """History log for purchase approval requests."""
    _name = "approval.request.purchase.history"
    _description = "Purchase Approval Request History"
    _order = "date desc"
    _rec_name = "action"

    # ============================================================================
    # FIELDS
    # ============================================================================

    request_id = fields.Many2one(
        "approval.request.purchase",
        string="Approval Request",
        required=True,
        ondelete="cascade"
    )

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True
    )

    action = fields.Selection([
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("refused", "Refused"),
        ("cancelled", "Cancelled"),
        ("reset", "Reset to Draft")
    ], string="Action", required=True)

    date = fields.Datetime(
        string="Date",
        required=True,
        default=fields.Datetime.now
    )

    comment = fields.Text(
        string="Comment"
    )