from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerHectaresRange(models.Model):
    _name = "res.partner.hectares.range"
    _description = "Partner Hectares Range"
    _order = "min_hectares"
    _rec_name = "display_name"

    name = fields.Char(
        string="Classification Name",
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )
    min_hectares = fields.Float(
        string="Minimum Hectares",
        required=True,
    )
    max_hectares = fields.Float(
        string="Maximum Hectares",
    )
    score_value = fields.Float(
        string="Score Points",
        required=True,
    )
    active = fields.Boolean(
        default=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )

    @api.constrains("min_hectares", "max_hectares")
    def _check_hectares_range(self):
        for record in self:
            if record.min_hectares < 0:
                raise ValidationError("Minimum hectares cannot be negative.")
            if record.max_hectares and record.max_hectares < record.min_hectares:
                raise ValidationError("Maximum hectares must be greater than minimum.")

    @api.constrains("min_hectares", "max_hectares", "active", "company_id")
    def _check_overlapping_ranges(self):
        for record in self:
            if not record.active:
                continue

            existing = self.search(
                [
                    ("id", "!=", record.id),
                    ("active", "=", True),
                    ("company_id", "=", record.company_id.id),
                ]
            )

            for other in existing:
                if self._ranges_overlap(record, other):
                    raise ValidationError(
                        f"Range {record.min_hectares}-{record.max_hectares or '∞'} "
                        f"overlaps with {other.min_hectares}-{other.max_hectares or '∞'}"
                    )

    @api.depends("name", "min_hectares", "max_hectares", "score_value")
    def _compute_display_name(self):
        for record in self:
            range_text = (
                f"{record.min_hectares} - {record.max_hectares}"
                if record.max_hectares
                else f"{record.min_hectares}+"
            )

            if record.name:
                record.display_name = (
                    f"{record.name} "
                    f"({range_text} hectares, "
                    f"{record.score_value} pts)"
                )
            else:
                record.display_name = (
                    f"{range_text} hectares " f"(Score: {record.score_value})"
                )

    def _ranges_overlap(self, range1, range2):
        min1, max1 = range1.min_hectares, range1.max_hectares or float("inf")
        min2, max2 = range2.min_hectares, range2.max_hectares or float("inf")
        return min1 <= max2 and max1 >= min2
