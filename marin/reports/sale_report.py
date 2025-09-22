# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleReport(models.Model):
    """Inheritance of sale.report to add customer profile fields for analysis.

    This extension adds customer profile information to the sales analysis report,
    including profile assignment, hectares, profile scores, and factor calculations.
    """

    _inherit = "sale.report"

    # ------------------------------------------------------------
    # ADDITIONAL FIELDS
    # ------------------------------------------------------------

    profile_id = fields.Many2one(
        comodel_name="res.partner.profile",
        string="Customer Profile",
        readonly=True,
        help="Customer profile assigned based on scoring system",
    )
    hectares = fields.Float(
        string="Hectares",
        readonly=True,
        aggregator="avg",
        help="Customer's total hectares",
    )
    score_hectares = fields.Float(
        string="Hectares Score",
        readonly=True,
        aggregator="avg",
        help="Score calculated from hectares",
    )
    score_categories = fields.Float(
        string="Categories Score",
        readonly=True,
        aggregator="avg",
        help="Score calculated from partner categories",
    )
    score_total = fields.Float(
        string="Total Score",
        readonly=True,
        aggregator="avg",
        help="Combined customer score",
    )

    # ------------------------------------------------------------
    # BUSINESS LOGIC
    # ------------------------------------------------------------

    def _select_additional_fields(self):
        """Hook to return additional fields SQL specification for select part.

        Returns:
            dict: Mapping field -> SQL computation of field
        """
        additional_fields = super()._select_additional_fields()

        additional_fields.update(
            {
                "profile_id": "partner.profile_id",
                "hectares": "COALESCE(partner.hectares, 0.0)",
                "score_hectares": "COALESCE(partner.score_hectares, 0.0)",
                "score_categories": "COALESCE(partner.score_categories, 0.0)",
                "score_total": "COALESCE(partner.score_total, 0.0)",
            }
        )

        return additional_fields

    def _from_sale(self):
        """Extend FROM clause to include profile data.

        Returns:
            str: Extended FROM clause with profile joins
        """
        from_clause = super()._from_sale()

        # The partner JOIN already exists in the base query, so we just need
        # to ensure we're getting the profile fields from the partner table
        return from_clause

    def _group_by_sale(self):
        """Extend GROUP BY clause to include profile fields.

        Returns:
            str: Extended GROUP BY clause
        """
        group_by_clause = super()._group_by_sale()

        # Add profile fields to GROUP BY
        group_by_clause += """,
            partner.profile_id,
            partner.hectares,
            partner.score_hectares,
            partner.score_categories,
            partner.score_total"""

        return group_by_clause
