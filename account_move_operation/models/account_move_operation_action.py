from odoo import api, fields, models


class AccountMoveOperationActions(models.Model):
    _name = "account.move.operation.action"
    _description = "Account Operation Actions"
    _order = "sequence, id"
    _check_company_auto = True


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "company_id" in fields_list and not res["company_id"]:
            res["company_id"] = self.env.company.id
        return res


    workflow_template_id = fields.Many2one(
        comodel_name="workflow.template",
        string="Route",
        required=True,
        ondelete="cascade",
        index=True
    )
    company_ids = fields.Many2many(
        related="workflow_template_id.company_ids",
        string="Companies",
    )
    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(
        default=True,
        help="If unchecked, it will allow you to hide the action without removing it."
    )
    sequence = fields.Integer(default=10)
    action = fields.Selection(
        selection=[
            ("move", "Create Journal Entry"),
            ("pay", "Create Payment"),
            ("reconcile", "Reconcile Payment"),
            ("operation", "Create Operation"),
            ("info", "Information"),
        ],
        required=True,
        index=True,
    )
    template_id = fields.Many2one(
        comodel_name="account.move.template",
        string="Move Template",
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
        domain=[("type", "in", ["bank", "cash"])],
        help="Set to have as default journal for payment.",
    )
    workflow_template_ids = fields.Many2many("workflow.template")
    date_last_document = fields.Boolean(
        help="When creating an invoice, set the date to be the same of the previous document, "
        "being it a payment or invoice."
    )
    diff_partner = fields.Boolean(
        string="Different Partner",
        help="Enables use of a different partner than the one set on the operation",
    )
    reconcile = fields.Boolean(
        help="Enable autoreconcile the created move with the selected bank statement.",
    )
    auto = fields.Boolean(
        default=True,
        help="Help simplify process avoiding using intermediary wizards.",
    )


    @api.onchange("workflow_template_id", "company_id")
    def _onchange_operation_type(self):
        """Ensure that the rule's company is the same than the route's company."""
        if self.workflow_template_id.company_id:
            self.company_id = self.workflow_template_id.company_id
