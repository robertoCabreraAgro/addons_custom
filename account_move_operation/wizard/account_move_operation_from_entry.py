from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveOperationFromEntry(models.TransientModel):
    _name = "account.move.operation.from.entry"
    _description = "Start Operation From Existing Entry"

    st_line_id = fields.Many2one(
        "account.bank.statement.line",
        string="Source Entry",
    )
    operation_type_id = fields.Many2one(
        "account.move.operation.type",
        string="Operation Type",
        required=True,
        domain="[('company_id', 'in', (company_id, False)), ('sub_operation', '=', False)]",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
    )
    reference = fields.Char(string="Reference")
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    company_id = fields.Many2one(
        "res.company",
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
    )
    multicompany = fields.Boolean(
        related="operation_type_id.multicompany",
    )
    diff_partner_id = fields.Many2one(
        "res.partner",
        string="Diff Partner",
        domain=["|", ("parent_id", "=", False), ("is_company", "=", True)],
    )
    target_company_id = fields.Many2one(
        "res.company",
        string="Target Company",
    )
    move_id = fields.Many2one(
        "account.move",
        string="Related Move",
        help="If this operation is related to a specific move, you can link it here.",
    )

    @api.model
    def default_get(self, fields_list):
        """Get default values from bank statement line context"""
        res = super().default_get(fields_list)
        move_id = self.env.context.get("default_move_id")
        _logger.info("default_get called with move_id: %s", move_id)
        if self.env.context.get(
            "active_model"
        ) == "account.bank.statement.line" and self.env.context.get("active_id"):
            st_line = self.env["account.bank.statement.line"].browse(
                self.env.context.get("active_id")
            )
            res.update(
                {
                    "st_line_id": st_line.id,
                    "partner_id": st_line.partner_id.id if st_line.partner_id else False,
                    "reference": st_line.payment_ref or st_line.ref,
                    "currency_id": st_line.currency_id.id or st_line.journal_id.currency_id.id or self.env.company.currency_id.id,
                    "amount": abs(st_line.amount),  # Use absolute value to get positive amount
                    "company_id": st_line.company_id.id,
                }
            )
        return res

    @api.onchange("operation_type_id")
    def _onchange_operation_type_id(self):
        """
        Load action lines. If starting from a BSL, mark the first step as executed for traceability.
        """
        self.ensure_one()
        self.action_line_ids = [(5, 0, 0)]  # Clear existing lines

        if not self.operation_type_id:
            return

        actions = self.operation_type_id.action_ids.filtered(lambda a: a.active)
        vals_list = []
        is_first_action = True
        for action in actions:
            # If this is the very first step AND we started from a bank statement line,
            # mark it as executed to maintain traceability.
            if is_first_action and self.st_line_id:
                vals_list.append(
                    {
                        "action_id": action.id,
                        "name": action.name,
                        "executed": True,
                        "document_id": self.st_line_id.id,
                    }
                )
                is_first_action = False
            else:
                # All other steps start as not executed.
                vals_list.append(
                    {
                        "action_id": action.id,
                        "name": action.name,
                        "executed": False,
                        "document_id": False,
                    }
                )

        if vals_list:
            self.action_line_ids = [(0, 0, vals) for vals in vals_list]

    def action_create_operation(self):
        """Create an operation and initialize it with our bank statement line"""
        self.ensure_one()

        operation_vals = {
            "name": _("New"),
            "operation_type_id": self.operation_type_id.id,
            "partner_id": self.partner_id.id,
            "reference": self.reference,
            "amount": self.amount,
            "currency_id": self.currency_id.id,
            "company_id": self.company_id.id,
            "st_line_id": self.st_line_id.id,  # Link to bank statement line
        }

        if self.diff_partner and self.diff_partner_id:
            operation_vals["diff_partner_id"] = self.diff_partner_id.id

        if self.multicompany and self.target_company_id:
            operation_vals["target_company_id"] = self.target_company_id.id

        operation = self.env["account.move.operation"].create(operation_vals)

        operation.action_start()

        # Mark user-selected executed actions as done and link documents
        for wizard_line in self.action_line_ids.filtered(lambda l: l.executed):
            operation_line = operation.line_ids.filtered(
                lambda l: l.action_id.id == wizard_line.action_id.id
            )
            if operation_line:
                # Based on the action type, link the correct document from the wizard.
                # NOTE: This assumes document_id is an account.bank.statement.line.
                # If other document types are needed, this logic should be expanded.
                if wizard_line.document_id:
                    if wizard_line.action_id.action == "reconcile":
                        operation_line.st_line_id = wizard_line.document_id.id
                    # Add elif for 'move' and 'pay' if they can also be source documents.
                    # For example:
                    # elif wizard_line.action_id.action == "move":
                    #     operation_line.move_id = wizard_line.document_id.id # This would require document_id to be a reference field.

                operation_line.state = "done"

                # Set next line to ready if exists
                next_line = operation.line_ids.filtered(
                    lambda l: l.orig_line_id.id == operation_line.id
                )
                if next_line:
                    next_line.state = "ready"

        return {
            "name": _("Account Operation"),
            "view_mode": "form",
            "res_model": "account.move.operation",
            "res_id": operation.id,
            "type": "ir.actions.act_window",
            "target": "current", # Open in the same window
        }


class AccountMoveOperationFromEntryLine(models.TransientModel):
    _name = "account.move.operation.from.entry.line"
    _description = "Operation From Entry Lines"

    wizard_id = fields.Many2one(
        "account.move.operation.from.entry",
        string="Wizard",
    )
    action_id = fields.Many2one(
        "account.move.operation.action",
        string="Action",
        required=True,
        readonly=True,
    )
    name = fields.Char(
        string="Description",
        required=True,
        readonly=True,
    )
    executed = fields.Boolean(
        string="Already Executed",
        help="""Mark the steps that have already been executed manually or through other processes.
                 Only the remaining steps will be executed when creating the operation.""",
    )
    document_id = fields.Many2one(
        "account.bank.statement.line",
        string="Existing Document",
    )
