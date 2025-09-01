from odoo import _, api, fields, models
from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import USAGE_SELECTION


class AccountMoveOperationFromEntry(models.TransientModel):
    _name = "account.move.operation.from.entry"
    _description = "Start Operation From Existing Entry"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    st_line_id = fields.Many2one(
        comodel_name="account.bank.statement.line",
        string="Source Entry",
    )
    operation_type_id = fields.Many2one(
        comodel_name="account.move.operation.type",
        string="Operation Type",
        required=True,
        domain="[('company_id', 'in', (company_id, False)), ('sub_operation', '=', False)]",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        required=True,
    )
    reference = fields.Char(string="Reference")
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    action_line_ids = fields.One2many(
        "account.move.operation.from.entry.line",
        "wizard_id",
        string="Actions",
    )
    diff_partner = fields.Boolean(
        related="operation_type_id.diff_partner",
        help="If the operation type allows a different partner, you can specify it here.",
    )
    multicompany = fields.Boolean(related="operation_type_id.multicompany")
    diff_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="CN Partner",
        domain=["|", ("parent_id", "=", False), ("is_company", "=", True)],
    )
    target_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Target Company",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Related Move",
        help="If this operation is related to a specific move, you can link it here.",
    )
    l10n_mx_edi_payment_method_id = fields.Many2one(
        comodel_name="l10n_mx_edi.payment.method",
        string="Método de pago SAT",
    )
    l10n_mx_edi_usage = fields.Selection(
        selection=USAGE_SELECTION,
        string="Uso del CFDI",
    )

    @api.model
    def default_get(self, fields_list):
        """Get default values from context and bank statement line"""
        res = super().default_get(fields_list)
        ctx = self.env.context

        if ctx.get("active_model") == "account.bank.statement.line" and ctx.get(
            "active_id"
        ):
            st_line = self.env["account.bank.statement.line"].browse(ctx["active_id"])
            res.update(
                {
                    "st_line_id": st_line.id,
                    "partner_id": st_line.partner_id.id or False,
                    "reference": st_line.payment_ref or st_line.ref,
                    "currency_id": (
                        st_line.currency_id.id
                        or st_line.journal_id.currency_id.id
                        or self.env.company.currency_id.id
                    ),
                    "amount": abs(st_line.amount),
                    "company_id": st_line.company_id.id,
                    "l10n_mx_edi_payment_method_id": st_line.l10n_mx_edi_payment_method_id.id,
                }
            )

        if ctx.get("default_diff_partner_id") and "diff_partner_id" in fields_list:
            res["diff_partner_id"] = ctx["default_diff_partner_id"]

        if ctx.get("l10n_mx_edi_usage") and "l10n_mx_edi_usage" in self._fields:
            res["l10n_mx_edi_usage"] = ctx["l10n_mx_edi_usage"]

        return res

    # ------------------------------------------------------------
    # ONCHANGE METHODS
    # ------------------------------------------------------------

    @api.onchange("operation_type_id")
    def _onchange_operation_type_id(self):
        """Load action lines. Mark first as executed if coming from BSL"""
        self.ensure_one()
        self.action_line_ids = [(5, 0, 0)]  # Clear existing lines

        if not self.operation_type_id:
            return

        actions = self.operation_type_id.action_ids.filtered("active")
        vals_list = []
        is_first = True
        for action in actions:
            vals = {
                "action_id": action.id,
                "name": action.name,
                "executed": is_first and bool(self.st_line_id),
                "document_id": (
                    self.st_line_id.id if is_first and self.st_line_id else False
                ),
            }
            vals_list.append(vals)
            is_first = False

        if vals_list:
            self.action_line_ids = [(0, 0, vals) for vals in vals_list]

    # ------------------------------------------------------------
    # ACTION METHODS
    # ------------------------------------------------------------

    def action_create_operation(self):
        """Create an operation from this wizard"""
        self.ensure_one()

        operation_vals = {
            "name": _("New"),
            "operation_type_id": self.operation_type_id.id,
            "partner_id": self.partner_id.id,
            "reference": self.reference,
            "amount": self.amount,
            "currency_id": self.currency_id.id,
            "company_id": self.company_id.id,
            "st_line_id": self.st_line_id.id,
            "l10n_mx_edi_payment_method_id": self.l10n_mx_edi_payment_method_id.id,
            "l10n_mx_edi_usage": self.l10n_mx_edi_usage,
        }

        if self.diff_partner and self.diff_partner_id:
            operation_vals["diff_partner_id"] = self.diff_partner_id.id

        if self.multicompany and self.target_company_id:
            operation_vals["target_company_id"] = self.target_company_id.id

        operation = self.env["account.move.operation"].create(operation_vals)
        operation.action_start()

        for wizard_line in self.action_line_ids.filtered("executed"):
            operation_line = operation.line_ids.filtered(
                lambda l: l.action_id.id == wizard_line.action_id.id
            )
            if operation_line:
                if (
                    wizard_line.document_id
                    and wizard_line.action_id.action == "reconcile"
                ):
                    operation_line.st_line_id = wizard_line.document_id.id

                operation_line.state = "done"

                next_line = operation.line_ids.filtered(
                    lambda l: l.orig_line_id.id == operation_line.id
                )
                if next_line:
                    next_line.state = "ready"

        return {
            "name": _("Account Operation"),
            "type": "ir.actions.act_window",
            "res_model": "account.move.operation",
            "view_mode": "form",
            "target": "current",
            "res_id": operation.id,
        }


class AccountMoveOperationFromEntryLine(models.TransientModel):
    _name = "account.move.operation.from.entry.line"
    _description = "Operation From Entry Lines"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    wizard_id = fields.Many2one(
        comodel_name="account.move.operation.from.entry",
        string="Wizard",
    )
    action_id = fields.Many2one(
        comodel_name="account.move.operation.action",
        string="Action",
        required=True,
        readonly=True,
    )
    name = fields.Char(string="Description", required=True, readonly=True)
    executed = fields.Boolean(string="Already Executed")
    document_id = fields.Many2one(
        comodel_name="account.bank.statement.line",
        string="Existing Document",
    )
