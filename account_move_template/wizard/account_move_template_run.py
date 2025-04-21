from ast import literal_eval
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _
from odoo.fields import Command

_logger = logging.getLogger(__name__)


class AccountMoveTemplateRun(models.TransientModel):
    _name = "account.move.template.run"
    _description = "Wizard to generate move from template"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    template_id = fields.Many2one(
        comodel_name="account.move.template",
        required=True,
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
    state = fields.Selection(
        [("select_template", "Select Template"), ("set_lines", "Set Lines")],
        default="select_template",
        readonly=True,
    )
    overwrite = fields.Text(
        help="""
             Valid dictionary to overwrite template lines:
             {'L1': {'partner_id': 1, 'amount': 100, 'name': 'some label'},
             'L2': {'partner_id': 2, 'amount': 200, 'name': 'some label 2'}, }
             """
    )
    price_unit = fields.Float(
        string="Unit Price",
        default=0.0,
    )
    ref = fields.Char(string="Reference")
    line_ids = fields.One2many(
        comodel_name="account.move.template.line.run",
        inverse_name="wizard_id",
        string="Lines",
    )

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if not self.template_id:
            return

        self.load_lines()

    def load_lines(self):
        self.ensure_one()
        self.line_ids.unlink()
        new_line_ids = self.env["account.move.template.line.run"]
        for tmpl_line in self.template_id.line_ids.filtered(
            lambda line: line.type == "input"
        ):
            new_line_ids += self.env["account.move.template.line.run"].new(
                self._prepare_wizard_line(tmpl_line)
            )
        self.line_ids = new_line_ids

    def create_move(self):
        self.ensure_one()
        company_cur = self.company_id.currency_id
        move_vals = self._prepare_move()
        for line in self.line_ids:
            amount = line.amount
            if not company_cur.is_zero(amount):
                move_vals["line_ids"].append(
                    Command.create(self._prepare_move_line(line, amount))
                )

        move = self.env["account.move"].create(move_vals)
        if hasattr(self, "price_unit") and self.price_unit:
            for move_line in move.line_ids:
                move_line.price_unit = self.price_unit

        result = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_journal_line"
        )
        result.update(
            {
                "name": _("Entry from template %s") % self.template_id.name,
                "res_id": move.id,
                "views": False,
                "view_id": False,
                "view_mode": "form,list",
                "context": self.env.context,
            }
        )
        return result

    def _prepare_move(self):
        journal = self.env["account.journal"].search(
            [("code", "=", self.template_id.journal_code)], limit=1
        )
        move_vals = {
            "company_id": self.company_id.id,
            "journal_id": journal.id,
            "move_type": self.template_id.move_type,
            "partner_id": self.partner_id.id or False,
            "date": self.date,
            "ref": self.ref,
            "line_ids": [],
        }
        return move_vals

    def _prepare_move_line(self, line, amount):

        debit = line.move_line_type == "dr"
        values = {
            "name": line.name,
            "account_id": line.account_id.id,
            "credit": 0.0 if debit else abs(amount),
            "debit": abs(amount) if debit else 0.0,
            "partner_id": line.partner_id.id or self.partner_id.id,
        }

        if hasattr(line, "price_unit") and line.price_unit:
            values["price_unit"] = line.price_unit
        elif hasattr(self, "price_unit") and self.price_unit:
            values["price_unit"] = self.price_unit

        if line.tax_ids:
            values["tax_ids"] = [Command.set(line.tax_ids.ids)]

        if getattr(line, "is_refund", False):
            tax_repartition = "refund_tax_id" if line.is_refund else "invoice_tax_id"
            atrl_ids = self.env["account.tax.repartition.line"].search(
                [
                    (tax_repartition, "in", line.tax_ids.ids),
                    ("repartition_type", "=", "base"),
                ]
            )
            if atrl_ids:
                values["tax_tag_ids"] = [Command.set(atrl_ids.mapped("tag_ids").ids)]

        if getattr(line, "tax_repartition_line_id", False):
            values["tax_repartition_line_id"] = line.tax_repartition_line_id.id
            values["tax_tag_ids"] = [
                Command.set(line.tax_repartition_line_id.tag_ids.ids)
            ]

        if getattr(line, "analytic_distribution", False):
            values["analytic_distribution"] = line.analytic_distribution

        overwrite = self._context.get("overwrite", {})
        move_line_vals = overwrite.get(f"L{line.sequence}", {})
        values.update(move_line_vals)

        self._update_account_on_negative(line, values)
        return values

    def _prepare_wizard_line(self, tmpl_line):
        account_id = self.env["account.account"].search(
            [("code_store", "=", tmpl_line.account_code)], limit=1
        )
        vals = {
            "wizard_id": self.id,
            "name": tmpl_line.name,
            "sequence": tmpl_line.sequence,
            "move_line_type": tmpl_line.move_line_type,
            "partner_id": tmpl_line.partner_id.id or False,
            "product_id": tmpl_line.product_id.id,
            "price_unit": tmpl_line.price_unit or False,
            "amount": 0.0,
            "account_id": account_id.id,
            "analytic_distribution": tmpl_line.analytic_distribution or False,
            "tax_ids": [Command.set(tmpl_line.tax_ids.ids)],
            "python_code": (
                tmpl_line.python_code if tmpl_line.type == "computed" else False
            ),
            "note": tmpl_line.note,
        }
        return vals
