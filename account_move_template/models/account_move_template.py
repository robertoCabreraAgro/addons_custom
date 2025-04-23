from odoo import api, fields, models
from odoo.tools.translate import _


class AccountMoveTemplate(models.Model):
    _name = "account.move.template"
    _description = "Journal Entry Template"
    _check_company_auto = True

    name = fields.Char(required=True, index=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
        check_company=True,
        readonly=False,
        store=False,
    )
    journal_code = fields.Char(
        string="Journal Code",
        required=True,
        help="When creating a new journal entry a journal having this code"
        "will be looked for",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        check_company=True,
    )
    invoice_payment_term_id = fields.Many2one(
        comodel_name="account.payment.term",
        string="Payment Terms",
        help="Used to compute the due date of the journal item.",
    )
    move_type = fields.Selection(
        selection=[
            ("entry", "Journal Entry"),
            ("in_invoice", "Vendor Bill"),
            ("in_refund", "Vendor Credit Note"),
            ("out_invoice", "Customer Invoice"),
            ("out_refund", "Customer Credit Note"),
        ],
        default="entry",
        required=True,
        help="Type of journal entry this template will create",
    )
    ref = fields.Char(
        string="Reference",
        help="Internal reference or note",
    )
    line_ids = fields.One2many(
        comodel_name="account.move.template.line",
        inverse_name="template_id",
        string="Lines",
    )
    is_payment = fields.Boolean(
        string="Is Payment",
        help="If checked, this template will generate a payment instead of a journal entry",
        default=False,
    )
    payment_type = fields.Selection(
        selection=[('outbound', 'Send Money'), ('inbound', 'Receive Money')],
        string="Payment Type",
        help="Determines the flow of the payment (outbound or inbound)",
    )
    partner_type = fields.Selection(
        selection=[('customer', 'Customer'), ('supplier', 'Vendor')],
        string="Partner Type",
        help="Determines whether the payment is for a customer or vendor",
    )
    payment_method_line_id = fields.Many2one(
        comodel_name="account.payment.method.line",
        string="Payment Method",
        domain="[('payment_type', '=', payment_type)]",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    payment_amount = fields.Monetary(
        string="Payment Amount",
        currency_field="currency_id",
        help="Default payment amount",
    )

    _sql_constraints = [
        (
            "name_company_unique",
            "unique(name, company_id)",
            "This name is already used by another template!",
        ),
    ]

    @api.onchange("is_payment")
    def _onchange_is_payment(self):
        """Update fields based on operation type"""
        if self.is_payment:
            # If we're changing to payment type, calculate a default amount from any existing lines
            total = 0.0
            for line in self.line_ids:
                if hasattr(line, 'balance') and line.balance:
                    total += line.balance
            if total != 0.0:
                self.payment_amount = abs(total)
                # Set payment type based on the calculated total
                self.payment_type = 'outbound' if total < 0 else 'inbound'
                # Set default partner type
                self.partner_type = 'supplier' if self.payment_type == 'outbound' else 'customer'
        

    def copy(self, default=None):
        """Override to set a different name when copying a template"""
        self.ensure_one()
        default = dict(default or {})
        default.update(name=_("%s (copy)") % self.name)
        return super().copy(default)

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        """Update payment method when journal changes"""
        if self.journal_id and self.payment_type:
            # Set the first available payment method for the selected journal
            payment_methods = self.env['account.payment.method.line'].search([
                ('journal_id', '=', self.journal_id.id),
                ('payment_type', '=', self.payment_type)
            ], limit=1)
            if payment_methods:
                self.payment_method_line_id = payment_methods[0].id
            else:
                self.payment_method_line_id = False

        if not self.journal_id:
            return

        self.journal_code = self.journal_id.code
        self.journal_id = False

    def action_move_template_run(self):
        """Open wizard to create move from template"""
        self.ensure_one()
        wizard = self.env["account.move.template.run"].create(
            {
                "template_id": self.id,
                "partner_id": self.partner_id.id,
                "date": fields.Date.context_today(self),
                "ref": self.ref,
                "payment_amount": self.payment_amount,
            }
        )
        wizard.load_lines()
        return {
            "name": _("Create Entry from Template"),
            "type": "ir.actions.act_window",
            "res_model": "account.move.template.run",
            "view_mode": "form",
            "target": "new",
            "res_id": wizard.id,
        }