import logging

from dateutil.relativedelta import relativedelta
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)


class SaleTargetWizard(models.TransientModel):
    """Sale Target Generation Wizard for mass target creation."""

    _name = "sale.target.wizard"
    _description = "Sale Target Generation Wizard"

    partner_ids = fields.Many2many(
        "res.partner",
        string="Clients",
        required=True,
        domain=[("is_company", "=", True), ("customer", "=", True)],
    )

    template_id = fields.Many2one(
        "sale.order.template",
        string="Quotation Template",
        required=True,
    )

    date_from = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.today,
    )

    date_to = fields.Date(
        string="End Date",
        required=True,
    )

    target_count = fields.Integer(
        string="Targets to Create", compute="_compute_summary", readonly=True
    )

    line_count = fields.Integer(
        string="Target Lines to Create", compute="_compute_summary", readonly=True
    )

    validation_errors = fields.Text(
        string="Validation Issues", compute="_compute_validation_errors", readonly=True
    )

    @api.depends("partner_ids", "template_id")
    def _compute_summary(self):
        """Compute summary counts for wizard."""
        for wizard in self:
            wizard.target_count = len(wizard.partner_ids)
            wizard.line_count = len(wizard.partner_ids) * len(
                wizard.template_id.sale_order_template_line_ids
            )

    @api.depends("partner_ids", "template_id", "date_from", "date_to")
    def _compute_validation_errors(self):
        """Compute validation errors for wizard."""
        for wizard in self:
            errors = []

            if (
                wizard.date_from
                and wizard.date_to
                and wizard.date_from >= wizard.date_to
            ):
                errors.append("End date must be after start date")

            partners_without_hectares = wizard.partner_ids.filtered(
                lambda p: not p.hectares
            )
            if partners_without_hectares:
                errors.append(
                    f"Partners without hectares: {', '.join(partners_without_hectares.mapped('name'))}"
                )

            partners_without_profile = wizard.partner_ids.filtered(
                lambda p: not p.profile_id
            )
            if partners_without_profile:
                errors.append(
                    f"Partners without profile: {', '.join(partners_without_profile.mapped('name'))}"
                )

            if (
                wizard.template_id
                and not wizard.template_id.sale_order_template_line_ids
            ):
                errors.append("Selected template has no product lines")

            if wizard.partner_ids and wizard.date_from and wizard.date_to:
                overlapping = self._check_overlapping_targets(wizard)
                if overlapping:
                    errors.append(
                        f"Overlapping targets found for: {', '.join(overlapping)}"
                    )

            wizard.validation_errors = "\n".join(errors) if errors else False

    def _check_overlapping_targets(self, wizard):
        """Check for overlapping targets in the date range."""
        overlapping_partners = []

        for partner in wizard.partner_ids:
            existing_targets = self.env["sale.target"].search(
                [
                    ("partner_id", "=", partner.id),
                    ("date_from", "<=", wizard.date_to),
                    ("date_to", ">=", wizard.date_from),
                ]
            )

            if existing_targets:
                overlapping_partners.append(partner.name)

        return overlapping_partners

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        """Validate date range."""
        for wizard in self:
            if (
                wizard.date_from
                and wizard.date_to
                and wizard.date_from >= wizard.date_to
            ):
                raise ValidationError(_("End date must be after start date."))

    def action_generate_targets(self):
        """Generate sale targets based on wizard configuration."""
        self.ensure_one()

        if self.validation_errors:
            raise UserError(
                _("Please resolve the following issues before proceeding:\n%s")
                % self.validation_errors
            )

        created_targets = self.env["sale.target"]

        for partner in self.partner_ids:
            target = self.env["sale.target"].create(
                {
                    "partner_id": partner.id,
                    "date_from": self.date_from,
                    "date_to": self.date_to,
                    "template_id": self.template_id.id,
                }
            )

            for template_line in self.template_id.sale_order_template_line_ids:
                if not template_line.product_id or template_line.display_type:
                    continue

                target_price = self._calculate_target_price(template_line, partner)

                self.env["sale.target.line"].create(
                    {
                        "target_id": target.id,
                        "product_id": template_line.product_id.id,
                        "quantity": template_line.product_uom_qty or 1.0,
                        "price_unit": target_price,
                    }
                )

            created_targets |= target

        return self._show_success_result(created_targets)

    def _calculate_target_price(self, template_line, partner):
        """Calculate target price using partner pricelist or fallback to list price."""
        if not template_line.product_id:
            return 0.0

        pricelist = partner.property_product_pricelist
        if pricelist:
            try:
                return pricelist.get_product_price(
                    template_line.product_id, 1.0, partner, date=fields.Date.today()
                )
            except:
                pass

        return template_line.product_id.list_price

    def _show_success_result(self, created_targets):
        """Show success notification and open created targets."""
        target_count = len(created_targets)
        line_count = sum(len(target.line_ids) for target in created_targets)

        message = _(
            "Successfully created %(target_count)d targets with %(line_count)d lines."
        ) % {"target_count": target_count, "line_count": line_count}

        action = self.env.ref("marin.action_sale_target").read()[0]
        action.update({"domain": [("id", "in", created_targets.ids)], "context": {}})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Targets Created"),
                "message": message,
                "type": "success",
                "next": action,
            },
        }
