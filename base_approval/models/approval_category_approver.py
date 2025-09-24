from odoo import api, fields, models


class ApprovalCategoryApprover(models.Model):
    """
    Approval Category Approver Model.

    This model serves as a many-to-many relationship between approval categories
    and users, with additional attributes for each approver assignment.

    It allows defining:
    - Which users can approve requests for a specific category
    - Whether each approver is required or optional
    - The sequence in which approvers should review (for sequential workflows)

    This design pattern enables flexible approval workflows where some approvers
    are mandatory while others are optional, and supports both parallel and
    sequential approval processes.
    """

    _name = "approval.category.approver"
    _description = "Approval Category Approver"
    _order = "sequence"
    _rec_name = "user_id"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("category_id")
    def _compute_existing_user_ids(self):
        """
        Compute list of users already assigned as approvers for this category.

        This method prevents duplicate user assignments within the same category
        by maintaining a list of users who are already approvers. The computed
        field is used in the domain of the user_id field to exclude already
        selected users from the selection.

        :return: None (sets existing_user_ids field)
        """
        for record in self:
            record.existing_user_ids = record.category_id.approver_ids.user_id
