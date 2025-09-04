# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResPartnerProfile(models.Model):
    """Model to classify customers through inherited tags from res.partner.category.

    This profile includes a percentage factor that will be used as a multiplier
    to calculate expected revenues and commercial targets. The system allows
    managing multiple profiles with defined precedence order.
    """

    _name = "res.partner.profile"
    _description = "Partner Profile"
    _order = "sequence, id"
    _rec_name = "name"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    name = fields.Char(
        string="Profile Name", required=True, help="Name of the customer profile"
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the profile will not appear in default views",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Used to order profiles. Lower values have higher precedence.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    category_ids = fields.Many2many(
        "res.partner.category",
        "res_partner_profile_category_rel",
        "profile_id",
        "category_id",
        string="Partner Tags",
        help="Partner categories associated with this profile",
    )
    factor = fields.Float(
        string="Factor",
        default=1.0,
        help="Multiplicative percentage factor (e.g., 1.2 for 120%)",
    )
    score_min = fields.Float(
        string="Minimum Score",
        default=0.0,
        help="Minimum score required for this profile",
    )
    score_max = fields.Float(
        string="Maximum Score", default=100.0, help="Maximum score for this profile"
    )

    @api.constrains("factor")
    def _check_factor(self):
        """Validate that the factor is greater than 0."""
        for profile in self:
            if profile.factor <= 0:
                raise ValidationError(
                    "The factor must be greater than 0. "
                    "Current value: %s" % profile.factor
                )

    @api.constrains("score_min", "score_max")
    def _check_score_range(self):
        """Validate score range values."""
        for profile in self:
            if profile.score_min < 0:
                raise ValidationError("Minimum score cannot be negative.")

            if profile.score_max < profile.score_min:
                raise ValidationError(
                    "Maximum score must be greater than or equal to minimum score."
                )

    @api.depends("name")
    def _compute_display_name(self):
        """Compute display name for the profile."""
        for profile in self:
            if profile.name:
                profile.display_name = profile.name
            else:
                profile.display_name = "New Profile"
