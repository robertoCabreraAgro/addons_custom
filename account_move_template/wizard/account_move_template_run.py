from ast import literal_eval
import logging
import math

from odoo import api, fields, models
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

    @api.onchange("template_id", "amount")
    def _onchange_template_or_amount(self):
        """
        Recalculate lines when the template or the total amount changes.
        """
        if self.template_id:
            self.load_lines()

    def load_lines(self):
        """
        Load and prepare the wizard lines from the selected template.
        This now extends the list of lines, as one template line can generate multiple wizard lines.
        """
        self.ensure_one()
        lines_to_create = []
        for tmpl_line in self.template_id.line_ids.filtered(lambda l: l.display_type == 'product'):
            lines_to_create.extend(self._prepare_wizard_line(tmpl_line))

        self.line_ids = [Command.clear()] + [Command.create(vals) for vals in lines_to_create]

    def create_payment(self):
        """Create a payment instead of a journal entry"""
        self.ensure_one()

        journal = self.env["account.journal"].search(
            [("code", "=", self.template_id.journal_code)], limit=1
        )

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
        """
        Create the account.move record from the wizard data.
        """
        self.ensure_one()
        if self.is_payment:
            return self.create_payment()

        company = self.multicompany_id or self.env.company
        move_env = self.env["account.move"].with_company(company)
        move_vals = self._prepare_move_vals(company)
        
        for line in self.line_ids:
            move_line_vals = self._prepare_move_line_vals(line)
            move_vals["line_ids"].append(Command.create(move_line_vals))

        move = move_env.with_context(default_move_type=self.move_type).create(move_vals)
        move._compute_amount()
        return move

    def _prepare_move_line_vals(self, line):
        """
        Prepare move line values from a wizard line.
        """
        vals = {
            "name": line.name,
            "account_id": line.account_id.id,
            "analytic_distribution": line.analytic_distribution,
            "partner_id": line.partner_id.id,
        }

        if self.template_id.move_type == "entry":
            vals["balance"] = self.balance or line.balance
        else:
            vals["product_id"] = line.product_id.id
            vals["quantity"] = line.quantity # No global override
            vals["price_unit"] = line.price_unit # No global override
            vals["discount"] = line.discount
            vals["tax_ids"] = [Command.set(line.tax_ids.ids)]

        _logger.info("Prepared move line vals: %s", vals)
        return vals

    def _prepare_move_vals(self, company):
        """Prepare the values for the account.move record itself."""
        journal = (
            self.env["account.journal"]
            .with_company(company)
            .search([("code", "=", self.template_id.journal_code)], limit=1)
        )

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

    def _prepare_wizard_line(self, tmpl_line):

        account_id = self.env["account.account"].search(
            [("code_store", "=", tmpl_line.account_code)], limit=1
        )

        price_unit, product, tax_ids = tmpl_line.price_unit, tmpl_line.product_id, tmpl_line.tax_ids
        
        if not product and tmpl_line.product_category_id:
            try:
                product = tmpl_line.get_random_product_for_category(tmpl_line.product_category_id)
                if not tmpl_line.price_unit:
                    price_unit = product.lst_price
                if not tmpl_line.tax_ids:
                    tax_ids = product.supplier_taxes_id
            except UserError as e:
                _logger.warning(e)

        final_price_unit = price_unit or (product.lst_price if product else 1.0)
        lines_to_return = []
        
        base_vals = {
            "wizard_id": self.id,
            "template_line_id": tmpl_line.id,
            "name": product.name if product else tmpl_line.name,
            "sequence": tmpl_line.sequence,
            "partner_id": tmpl_line.partner_id.id or False,
            "account_id": account_id.id,
            "analytic_distribution": tmpl_line.analytic_distribution or None,
            "product_id": product.id if product else False,
            "product_uom_id": product.uom_id.id if product else False,
            "discount": tmpl_line.discount or False,
            "balance": tmpl_line.balance or False,
            "tax_ids": [Command.set(tax_ids.ids)],
        }

        if self.amount and final_price_unit > 0:
            currency = self.env.company.currency_id
            
            quantity_int = math.floor(self.amount / final_price_unit)

            if quantity_int > 0:
                # First line with the integer quantity
                first_line_vals = base_vals.copy()
                first_line_vals.update({
                    "quantity": quantity_int,
                    "price_unit": final_price_unit,
                })
                lines_to_return.append(first_line_vals)

                # Calculate remainder without intermediate rounding
                subtotal1 = quantity_int * final_price_unit
                remainder = self.amount - subtotal1

                # Check if remainder is significant before creating a new line
                if not currency.is_zero(remainder):
                    second_line_vals = base_vals.copy()
                    second_line_vals.update({
                        "name": f"{base_vals['name']} (promotion)",
                        "quantity": 1,
                        "price_unit": remainder,
                        "sequence": tmpl_line.sequence + 1,
                    })
                    lines_to_return.append(second_line_vals)
            else:
                # If amount is less than one unit, create one line for the total amount
                single_line_vals = base_vals.copy()
                single_line_vals.update({
                    "quantity": 1,
                    "price_unit": self.amount,
                })
                lines_to_return.append(single_line_vals)
        else:
            # Fallback if amount is not set
            fallback_vals = base_vals.copy()
            fallback_vals.update({
                "quantity": tmpl_line.quantity,
                "price_unit": final_price_unit,
            })
            lines_to_return.append(fallback_vals)

        return lines_to_return
