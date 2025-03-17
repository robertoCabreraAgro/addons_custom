from odoo import api, fields, models


class ApprovalCategoryApprover(models.Model):
    """Intermediate model between approval.category and res.users
    To know whether an approver for this category is required or not"""

    _name = "approval.category.approver"
    _description = "Approval Category Approver"
    _order = "sequence"
    _rec_name = "user_id"

    category_id = fields.Many2one(
        comodel_name="approval.category",
        string="Approval Category",
        required=True,
        ondelete="cascade",
    )
    existing_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_existing_user_ids",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        check_company=True,
        domain="[('id', 'not in', existing_user_ids)]",
        ondelete="cascade",
    )
    sequence = fields.Integer("Sequence", default=10)
    required = fields.Boolean(default=False)

    @api.depends("category_id")
    def _compute_existing_user_ids(self):
        for record in self:
            record.existing_user_ids = record.category_id.approver_ids.user_id
