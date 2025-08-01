from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleTarget(models.Model):
    """Sales target management for customer objectives by period.

    This model stores sales targets for customers based on agricultural seasons,
    calculating target amounts using customer profiles, hectares, and quotation templates.
    """

    _name = "sale.target"
    _description = "Sales Target"
    _order = "date_from desc, partner_id"
    _rec_name = "name"

    name = fields.Char(
        string="Target Name",
        compute="_compute_name",
        store=True,
        help="Computed name based on partner, template and period",
    )

    date_from = fields.Date(required=True, help="Start date of the target period")

    date_to = fields.Date(required=True, help="End date of the target period")

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        help="Customer for this sales target",
    )

    template_id = fields.Many2one(
        "sale.order.template",
        string="Quotation Template",
        required=True,
        help="Template used to calculate target quantities and amounts",
    )

    season_id = fields.Many2one(
        "date.range",
        string="Agricultural Season",
        related="template_id.season_id",
        store=True,
        readonly=True,
        help="Agricultural season from the selected quotation template",
    )

    profile_id = fields.Many2one(
        "res.partner.profile",
        string="Customer Profile",
        related="partner_id.profile_id",
        store=True,
        readonly=True,
        help="Customer profile used for factor calculation",
    )

    hectares = fields.Float(
        string="Hectares",
        related="partner_id.hectares",
        readonly=True,
        help="Customer's hectares for target quantity calculation",
    )

    factor = fields.Float(
        string="Profile Factor",
        related="profile_id.factor",
        readonly=True,
        help="Factor from customer profile for quantity adjustment",
    )

    target_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        help="Total target amount calculated from all lines",
    )

    line_ids = fields.One2many(
        "sale.target.line",
        "target_id",
        string="Target Lines",
        help="Detailed target lines by product",
    )

    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        related="partner_id.user_id",
        store=True,
        readonly=True,
        help="Assigned salesperson from customer record",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )

    @api.depends("partner_id", "template_id", "date_from", "date_to")
    def _compute_name(self):
        """Compute display name based on partner, template and period."""
        for target in self:
            if target.partner_id and target.template_id and target.date_from and target.date_to:
                target.name = (
                    f"{target.partner_id.name} - {target.template_id.name} ({target.date_from} - {target.date_to})"
                )
            else:
                target.name = "New Sales Target"

    @api.depends("line_ids.target_amount")
    def _compute_amounts(self):
        """Calculate total target amount from all lines."""
        for target in self:
            target.target_amount = sum(target.line_ids.mapped("target_amount"))

    @api.constrains("date_from", "date_to", "partner_id")
    def _check_overlapping_periods(self):
        """Prevent overlapping date periods for the same partner."""
        for target in self:
            if target.date_from and target.date_to and target.partner_id:
                if target.date_from > target.date_to:
                    raise ValidationError(self.env._("End date must be after start date."))

                overlapping = self.search(
                    [
                        ("id", "!=", target.id),
                        ("partner_id", "=", target.partner_id.id),
                        "|",
                        "&",
                        ("date_from", "<=", target.date_from),
                        ("date_to", ">=", target.date_from),
                        "&",
                        ("date_from", "<=", target.date_to),
                        ("date_to", ">=", target.date_to),
                    ]
                )

                if overlapping:
                    raise ValidationError(
                        f"There is already a sales target for customer {target.partner_id.name} "
                        f"in the period from {overlapping[0].date_from} to {overlapping[0].date_to}. "
                        "Target periods cannot overlap for the same customer."
                    )
