import base64

from odoo import api, fields, models, tools
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


CATEGORY_SELECTION = [
    ("required", "Required"),
    ("optional", "Optional"),
    ("no", "None"),
]


class ApprovalCategory(models.Model):
    _name = "approval.category"
    _description = "Approval Category"
    _check_company_auto = True
    _order = "sequence, id"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        copy=False,
        index=True,
    )
    name = fields.Char(
        string="Name",
        translate=True,
        required=True,
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string="Sequence")
    automated_sequence = fields.Boolean(
        string="Automated Sequence?",
        help="If checked, the Approval Requests will have an automated "
        "generated name based on the given code.",
    )
    sequence_code = fields.Char(string="Code")
    sequence_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Reference Sequence",
        check_company=True,
        copy=False,
    )
    image = fields.Binary(
        string="Image",
        default=lambda self: self._get_default_image(),
    )
    description = fields.Char(string="Description", translate=True)

    has_date = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Date",
        required=True,
        default="no",
    )
    has_date_deadline = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Date Deadline",
        required=True,
        default="no",
    )
    has_period = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Period",
        required=True,
        default="no",
    )
    has_partner = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Contact",
        required=True,
        default="no",
    )
    has_payment_method = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Payment",
        required=True,
        default="no",
    )
    has_product = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Product",
        required=True,
        default="no",
        help="Additional products that should be specified on the request.",
    )
    has_quantity = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Quantity",
        required=True,
        default="no",
    )
    has_amount = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Amount",
        required=True,
        default="no",
    )
    has_reference = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Reference",
        required=True,
        default="no",
        help="An additional reference that should be specified on the request.",
    )
    has_location = fields.Selection(
        CATEGORY_SELECTION,
        string="Has Location",
        required=True,
        default="no",
    )
    requirer_document = fields.Selection(
        [("required", "Required"), ("optional", "Optional")],
        string="Documents",
        required=True,
        default="optional",
    )
    approval_minimum = fields.Integer(
        string="Minimum Approval",
        required=True,
        default="1",
    )
    manager_approval = fields.Selection(
        [("approver", "Is Approver"), ("required", "Is Required Approver")],
        string="Employee's Manager",
        help="""How the employee's manager interacts with this type of approval.

        Empty: do nothing
        Is Approver: the employee's manager will be in the approver list
        Is Required Approver: the employee's manager will be required to approve the request.
        """,
    )
    approval_type = fields.Selection(
        string="Approval Type",
        selection=[],
        help="Allows you to define which documents you would like "
        "to create once the request has been approved",
    )
    approve_sequentially = fields.Boolean(
        string="Approvers Sequence?",
        help="If checked, the approvers have to approve in sequence (one after the other). "
        "If Employee's Manager is selected as approver, they will be the first in line.",
    )
    approver_ids = fields.One2many(
        comodel_name="approval.category.approver",
        inverse_name="category_id",
        string="Approvers",
    )
    group_ids = fields.Many2many(
        comodel_name="res.groups",
        string="Groups",
    )
    invalid_minimum = fields.Boolean(compute="_compute_invalid_minimum")
    invalid_minimum_warning = fields.Char(compute="_compute_invalid_minimum")
    count_request_to_validate = fields.Integer(
        string="Number of requests to validate",
        compute="_compute_count_request_to_validate",
    )

    # ------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------

    @api.constrains("approval_minimum", "approver_ids")
    def _constrains_approval_minimum(self):
        for category in self:
            if category.approval_minimum < len(
                category.approver_ids.filtered("required")
            ):
                raise ValidationError(
                    _(
                        "Minimum Approval must be equal or superior to the sum of required Approvers."
                    )
                )

    @api.constrains("approver_ids")
    def _constrains_approver_ids(self):
        # There seems to be a problem with how the database is updated which doesn't let use to an sql constraint for this
        # Issue is: records seem to be created before others are saved, meaning that if you originally have only user a
        #  change user a to user b and add a new line with user a, the second line will be created and will trigger the constraint
        #  before the first line will be updated which wouldn't trigger a ValidationError
        for category in self:
            if len(category.approver_ids) != len(category.approver_ids.user_id):
                raise ValidationError(
                    _("An user may not be in the approver list multiple times.")
                )

    @api.constrains("approve_sequentially", "approval_minimum")
    def _constrains_approve_sequentially(self):
        if any(a.approve_sequentially and not a.approval_minimum for a in self):
            raise ValidationError(
                _(
                    "Approver Sequence can only be activated with at least 1 minimum approver."
                )
            )

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("automated_sequence"):
                sequence = self.env["ir.sequence"].create(
                    {
                        "name": _("Sequence %(code)s", code=vals["sequence_code"]),
                        "padding": 5,
                        "prefix": vals["sequence_code"],
                        "company_id": vals.get("company_id"),
                    }
                )
                vals["sequence_id"] = sequence.id
        return super().create(vals_list)

    def write(self, vals):
        if "sequence_code" in vals:
            for category in self:
                sequence_vals = {
                    "name": _("Sequence %(code)s", code=vals["sequence_code"]),
                    "padding": 5,
                    "prefix": vals["sequence_code"],
                }
                if category.sequence_id:
                    category.sequence_id.write(sequence_vals)
                else:
                    sequence_vals["company_id"] = vals.get(
                        "company_id", category.company_id.id
                    )
                    sequence = self.env["ir.sequence"].create(sequence_vals)
                    category.sequence_id = sequence
        if "company_id" in vals:
            for category in self:
                if category.sequence_id:
                    category.sequence_id.company_id = vals.get("company_id")
        return super().write(vals)

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_count_request_to_validate(self):
        domain = [
            ("state", "=", "pending"),
            ("approver_ids.user_id", "=", self.env.user.id),
        ]
        requests_data = self.env["approval.request"]._read_group(
            domain,
            ["category_id"],
            ["__count"],
        )
        requests_mapped_data = {category.id: count for category, count in requests_data}
        for category in self:
            category.count_request_to_validate = requests_mapped_data.get(
                category.id, 0
            )

    @api.depends_context("lang")
    @api.depends("approval_minimum", "manager_approval", "approver_ids")
    def _compute_invalid_minimum(self):
        for category in self:
            if category.approval_minimum > len(category.approver_ids) + int(
                bool(category.manager_approval)
            ):
                category.invalid_minimum = True
            else:
                category.invalid_minimum = False
            category.invalid_minimum_warning = category.invalid_minimum and _(
                "Your minimum approval exceeds the total of default approvers."
            )

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def create_request(self):
        self.ensure_one()
        # If category uses sequence, set next sequence as name
        # (if not, set category name as default name).
        return {
            "type": "ir.actions.act_window",
            "res_model": "approval.request",
            "views": [[False, "form"]],
            "context": {
                "default_name": _("New") if self.automated_sequence else self.name,
                "default_category_id": self.id,
                "default_request_owner_id": self.env.user.id,
                "default_state": "new",
            },
        }

    def _get_default_image(self):
        default_image_path = "base_approval/static/src/img/Folder.png"
        return base64.b64encode(tools.misc.file_open(default_image_path, "rb").read())
