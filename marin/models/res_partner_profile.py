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

    name = fields.Char(
        string="Profile Name", required=True, help="Name of the customer profile"
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

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Used to order profiles. Lower values have higher precedence.",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the profile will not appear in default views",
    )

    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
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

    @api.depends("name")
    def _compute_display_name(self):
        """Compute display name for the profile."""
        for profile in self:
            if profile.name:
                profile.display_name = profile.name
            else:
                profile.display_name = "New Profile"
