from ast import literal_eval
import logging

from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _
from odoo.fields import Command

_logger = logging.getLogger(__name__)


class AccountMoveTemplateRun(models.TransientModel):
    _name = "account.move.template.run"
    _description = "Wizard to generate move from template"

    template_id = fields.Many2one(
        comodel_name="account.move.template",
        required=True,
    )
    move_type = fields.Selection(
        related="template_id.move_type",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]",
    )
    date = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )
    overwrite = fields.Text(
        help="""
             Valid dictionary to overwrite template lines:
             {'L1': {'partner_id': 1, 'amount': 100, 'name': 'some label'},
             'L2': {'partner_id': 2, 'amount': 200, 'name': 'some label 2'}, }
             """
    )
    quantity = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
        default=False,
    )
    price_unit = fields.Float(
        string="Unit Price",
        digits="Product Price",
        default=False,
    )
    discount = fields.Float(
        string="Discount (%)",
        digits="Discount",
        default=False,
    )
    balance = fields.Float(
        string="Balance",
        digits="Product Price",
        default=False,
    )
    ref = fields.Char(string="Reference")
    line_ids = fields.One2many(
        comodel_name="account.move.template.line.run",
        inverse_name="wizard_id",
        string="Lines",
    )
    is_payment = fields.Boolean(
        related="template_id.is_payment",
        readonly=True,
    )
    payment_type = fields.Selection(
        related="template_id.payment_type",
        readonly=True,
    )
    partner_type = fields.Selection(
        related="template_id.partner_type",
        readonly=True,
    )
    diff_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Different Partner",
        help="Optional partner different from the operation's main partner.",
    )
    multicompany_id = fields.Many2one(
        comodel_name="res.company",
        string="Multicompany Target",
        help="Target company to use when creating the journal entry, if different.",
    )
    amount = fields.Float(string="Amount")

    @api.model
    @tools.ormcache('company_id', 'journal_code')
    def _get_journal_id(self, company_id, journal_code):
        """Return the journal id matching ``journal_code`` in ``company_id``."""
        journal = (
            self.env["account.journal"].with_company(company_id).search(
                [("code", "=", journal_code)], limit=1
            )
        )
        return journal.id

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.template_id:
            self.load_lines()

    def load_lines(self):
        self.ensure_one()
        tmpl_lines = self.template_id.line_ids.filtered(lambda line: line.type == "input")
        account_codes = [l.account_code for l in tmpl_lines if l.account_code]
        accounts = self.env["account.account"].search([
            ("code_store", "in", account_codes)
        ])
        account_map = {acc.code_store: acc.id for acc in accounts}

        lines = [
            (0, 0, self._prepare_wizard_line(tmpl_line, account_map.get(tmpl_line.account_code)))
            for tmpl_line in tmpl_lines
        ]
        self.line_ids = [(5, 0, 0)] + lines


    def create_payment(self):
        """Create a payment instead of a journal entry"""
        self.ensure_one()

        journal_id = self._get_journal_id(
            self.env.company.id, self.template_id.journal_code
        )
        journal = self.env["account.journal"].browse(journal_id)

        if not journal:
            raise UserError(_("No valid journal found for this payment."))

        payment_vals = {
            "date": self.date,
            "payment_type": self.payment_type,
            "partner_type": self.partner_type,
            "partner_id": (self.diff_partner_id or self.partner_id).id,
            "journal_id": journal.id,
            "amount": self.amount or 0.0,
        }

        payment = self.env["account.payment"].create(payment_vals)
        payment.action_post()

        return payment

    def create_move(self):
        _logger.info("self %s", self.read())
        self.ensure_one()
        if self.is_payment:
            return self.create_payment()
        company = self.multicompany_id or self.env.company
        _logger.info("company %s", company)
        move_env = self.env["account.move"].with_company(company)
        move_vals = self._prepare_move_vals(company)
        _logger.info("move_vals %s", move_vals)
        for line in self.line_ids:
            move_vals["line_ids"].append(
                Command.create(self._prepare_move_line_vals(line))
            )
        move = move_env.with_context(default_move_type=self.move_type).create(move_vals)
        move.invoice_line_ids._compute_tax_ids()
        return move

    def _prepare_move_line_vals(self, line):
        """Assemble values for a single journal line created from ``line``."""

        vals = {
            "name": line.name,
            "account_id": line.account_id.id,
            "analytic_distribution": line.analytic_distribution,
        }

        partner = line.partner_id or self.diff_partner_id or self.partner_id
        if partner:
            vals["partner_id"] = partner.id
        if self.template_id.move_type == "entry":
            vals["balance"] = self.balance or line.balance

        elif self.template_id.move_type != "entry":
            vals["product_id"] = line.product_id.id
            vals["quantity"] = self.quantity or line.quantity
            vals["price_unit"] = (
                self.amount or self.price_unit or line.price_unit or 0.0
            )
            vals["discount"] = self.discount or line.discount

        return vals

    def _prepare_move_vals(self, company):
        journal_id = self._get_journal_id(company.id, self.template_id.journal_code)
        journal = self.env["account.journal"].browse(journal_id)

        if not journal:
            raise UserError(
                _(
                    "No valid journal found for this journal code in the selected company."
                )
            )

        return {
            "journal_id": journal.id,
            "move_type": self.template_id.move_type,
            "partner_id": (self.diff_partner_id or self.partner_id).id or False,
            "invoice_payment_term_id": self.template_id.invoice_payment_term_id.id
            or False,
            "date": self.date,
            "ref": self.ref,
            "company_id": company.id,
            "line_ids": [],
        }

    def _prepare_wizard_line(self, tmpl_line, account_id=None):
        """Return values for a wizard line mirrored from ``tmpl_line``."""

        if account_id is None:
            account = self.env["account.account"].search(
                [("code_store", "=", tmpl_line.account_code)], limit=1
            )
            account_id = account.id
        vals = {
            "wizard_id": self.id,
            "name": tmpl_line.name,
            "sequence": tmpl_line.sequence,
            "partner_id": tmpl_line.partner_id.id or False,
            "account_id": account_id,
            "analytic_distribution": tmpl_line.analytic_distribution or False,
            "product_id": tmpl_line.product_id.id or False,
            "product_uom_id": tmpl_line.product_uom_id.id or False,
            "quantity": tmpl_line.quantity or False,
            "price_unit": tmpl_line.price_unit or False,
            "discount": tmpl_line.discount or False,
            "balance": tmpl_line.balance or False,
            "python_code": (
                tmpl_line.python_code if tmpl_line.type == "computed" else False
            ),
            "note": tmpl_line.note,
        }
        return vals
