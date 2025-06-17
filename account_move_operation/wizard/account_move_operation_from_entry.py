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
        """Load action lines based on operation type"""
        self.ensure_one()
        self.action_line_ids = [(5, 0, 0)]

        if not self.operation_type_id:
            return

        actions = self.operation_type_id.action_ids.filtered(lambda a: a.active)

        # For bank statement lines, we typically start with reconcile or payment actions
        matched_action = self._identify_matching_action(actions)

        vals_list = []
        for action in actions:
            _logger.info("action %s", action.read())
            is_source = action == matched_action
            vals_list.append(
                {
                    "action_id": action.id,
                    "name": action.name,
                    "executed": is_source,
                    "document_id": self.st_line_id.id if is_source else False,
                }
            )
        _logger.info("Action lines to assign: %s", vals_list)

        self.action_line_ids = [(0, 0, vals) for vals in vals_list]

    def _identify_matching_action(self, actions):
        """Try to identify which action matches our bank statement line"""
        self.ensure_one()
        st_line = self.st_line_id

        if not st_line:
            return actions.filtered(lambda a: a.action == "reconcile")[:1]

        # If the amount is positive (credit), it's likely a payment received
        if st_line.amount > 0:
            # Look for reconcile actions first (most common for incoming payments)
            reconcile_actions = actions.filtered(lambda a: a.action == "reconcile")
            if reconcile_actions:
                return reconcile_actions[:1]
        else:
            # If negative (debit), it's likely a payment made
            pay_actions = actions.filtered(lambda a: a.action == "pay")
            if pay_actions:
                return pay_actions[:1]

        # Default to first action if nothing matches
        return actions[:1] if actions else self.env["account.move.operation.action"]

    def action_create_operation(self):
        """Create an operation and initialize it with our bank statement line"""
        self.ensure_one()

        if all(line.executed for line in self.action_line_ids):
            raise ValidationError(
                _("All actions are already executed. No need to create an operation.")
            )

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

        # Mark executed actions as done and link documents
        for wizard_line in self.action_line_ids.filtered(lambda l: l.executed):
            operation_line = operation.line_ids.filtered(
                lambda l: l.action_id.id == wizard_line.action_id.id
            )
            if operation_line:
                # For reconcile actions, link the bank statement line
                if wizard_line.action_id.action == "reconcile":
                    operation_line.st_line_id = wizard_line.document_id.id
                elif wizard_line.action_id.action == "move":
                    # If somehow we have a move linked
                    operation_line.move_id = wizard_line.document_id.id
                elif wizard_line.action_id.action == "pay":
                    # If we have a payment linked
                    operation_line.payment_id = wizard_line.document_id.id

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