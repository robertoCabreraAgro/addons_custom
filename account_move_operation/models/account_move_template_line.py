from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMoveTemplateLine(models.Model):
    _inherit = "account.move.template.line"

    move_type = fields.Selection(related="template_id.move_type", store=True)
    product_id = fields.Many2one(
        "product.product", domain="[('company_id', 'in', [company_id, False])]", check_company=True
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        "Unit of Measure",
        compute="_compute_product_uom_id",
        store=True,
        readonly=False,
        precompute=True,
        domain="[('category_id', '=', product_uom_category_id)]",
    )
    product_uom_category_id = fields.Many2one(related="product_id.uom_id.category_id")
    product_uom_qty = fields.Float("Quantity", digits="Product Unit of Measure", default=1)
    amount = fields.Monetary(currency_field="company_currency_id", default=0)

    @api.constrains("type", "python_code")
    def check_python_code(self):
        for line in self:
            if line.type == "computed" and not line.python_code:
                raise ValidationError(_("Python Code must be set for computed line with sequence %d.", line.sequence))

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id

    @api.onchange("type")
    def _onchange_type(self):
        for line in self:
            if line.type == "computed":
                line.amount = 0

    @api.depends("partner_id", "account_id", "product_id")
    def _compute_analytic_distribution(self):
        for line in self:
            distribution = self.env["account.analytic.distribution.model"]._get_distribution(
                {
                    "partner_id": line.partner_id.id,
                    "partner_category_id": line.partner_id.category_id.ids,
                    "product_id": line.product_id.id,
                    "product_categ_id": line.product_id.categ_id.id,
                    "account_prefix": line.account_id.code,
                    "company_id": line.company_id.id,
                }
            )
            line.analytic_distribution = distribution or line.analytic_distribution

    def _safe_overwrite_vals(self, model, vals):
        obj = self.env[model]
        copy_vals = vals.copy()
        invalid_keys = list(set(list(vals.keys())) - set(list(dict(obj._fields).keys())))
        for key in invalid_keys:
            copy_vals.pop(key)
        return copy_vals

    def _prepare_wizard_line_vals(self, overwrite_vals):
        vals = {
            "line_id": self.id,
            "partner_id": self.partner_id.id or False,
            "product_id": self.product_id.id or False,
            "product_uom_id": self.product_uom_id.id or self.product_id.uom_id.id or False,
            "product_uom_qty": self.product_uom_qty or 1.0,
            "name": self.name,
            "account_id": self.account_id.id,
            "amount": self.amount,
            "tax_ids": [Command.set(self.tax_ids.ids)],
            "type": self.type,
        }
        if overwrite_vals:
            safe_overwrite_vals = self._safe_overwrite_vals(
                self._name, overwrite_vals.get("L{}".format(self.sequence), {})
            )
            vals.update(safe_overwrite_vals)
        return vals
