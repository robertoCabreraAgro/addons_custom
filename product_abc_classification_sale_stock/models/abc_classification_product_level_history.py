# Copyright 2021 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
import re


class AbcClassificationProductLevelHistory(models.Model):
    """ABC Classification Product Level History

    This model is used to display the history of values collected and involved
    into the computation of the ABC classification level.

    To avoid performance issue, the table is populated by bypassing the ORM
    since a new line is inserted by product and classification profile,
    each time the computation of the classification levels occurs.

    Some could argue that the same functionality could be achieved by using the
    tracking of changes mechanism provided by mail.thread. Nevertheless,
    mail.thread introduce a to high performance footprint and the result is not
    usable into reports
    """

    _name = "abc.classification.product.level.history"
    _description = "ABC Classification Product Level History"

    computed_level_id = fields.Many2one(
        "abc.classification.level",
        string="Computed classification level",
        readonly=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        index=True,
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product template",
        related="product_id.product_tmpl_id",
        readonly=True,
        store=True,
    )
    profile_id = fields.Many2one(
        "abc.classification.profile",
        string="Profile",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    product_level_id = fields.Many2one(
        "abc.classification.product.level",
        required=True,
        index=True,
        readonly=True,
        ondelete="cascade",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        "Warehouse",
        readonly=False,
        ondelete="cascade",
    )
    ranking = fields.Integer(
        required=True,
        readonly=True,
        help="Ranking by number of oder lines",
    )
    number_so_lines = fields.Integer(
        "Number of sale order lines",
        required=True,
        readonly=True,
    )
    total_so_lines = fields.Integer(
        "Total of sale order lines",
        required=True,
        readonly=True,
    )
    percentage = fields.Float(
        required=True,
        readonly=True,
        help="Percentage of total sale order lines",
        digits=(7, 4),
        aggregator="sum",
    )
    cumulated_percentage = fields.Float(
        required=True,
        readonly=True,
        help="Cumulated percentage of all the products with a better ranking",
        digits=(7, 4),
        aggregator=None,
    )
    total_products = fields.Integer(
        "Total products analysed",
        required=True,
        readonly=True,
        aggregator=None,
    )
    percentage_products = fields.Float(
        "Percentage of products",
        required=True,
        readonly=True,
        help="Percentage of total products analyzed",
        digits=(7, 4),
        aggregator="sum",
    )
    cumulated_percentage_products = fields.Float(
        "Cumulated percentage of products",
        required=True,
        readonly=True,
        help="Cumulated percentage of total products analyzed with a " "better ranking",
        digits=(7, 4),
        aggregator=None,
    )
    sum_cumulated_percentages = fields.Float(
        "Sum of cummulated percentages",
        required=True,
        readonly=True,
        help="Sum cumulated % so lines and cumulated % products",
        aggregator=None,
    )
    from_date = fields.Date(readonly=True)
    to_date = fields.Date(readonly=True)
    season_id = fields.Many2one(
        "date.range",
        string="Season",
        readonly=True,
        help="Specific season (date range) for this ABC classification record",
    )

    classification_variance = fields.Float(
        string="Classification Variance",
        compute="_compute_classification_variance",
        store=True,
        help="Variation between seasons for this product",
        digits=(7, 4),
    )

    season_performance = fields.Float(
        string="Season Performance",
        compute="_compute_season_performance",
        store=True,
        help="Performance indicator for seasonal patterns",
        digits=(7, 4),
    )

    strategic_segment = fields.Selection(
        [
            ("seasonal_star", "Seasonal Star"),
            ("business_pillar", "Business Pillar"),
            ("seasonal_niche", "Seasonal Niche"),
            ("marginal_product", "Marginal Product"),
        ],
        string="Strategic Segment",
        compute="_compute_strategic_segment",
        store=True,
        help="""Automatic categorization based on classification variance and seasonal performance:
        
• Seasonal Star (variance ≥1, performance >15): Dynamic stock + temporary promotion
• Business Pillar (variance =0, performance >10): Constant stock + protection
• Seasonal Niche (variance ≥1, performance 1-10): Minimum seasonal stock  
• Marginal Product (variance ≤1, performance <1): Discontinuation candidate""",
    )

    @api.depends("product_id", "computed_level_id")
    def _compute_classification_variance(self):
        """Calculate variance in classification across different seasons for the same product."""
        for record in self:
            if not record.product_id:
                record.classification_variance = 0.0
                continue

            # Get all classifications for this product across different seasons
            same_product_records = self.search(
                [
                    ("product_id", "=", record.product_id.id),
                    (
                        "warehouse_id",
                        "=",
                        record.warehouse_id.id if record.warehouse_id else False,
                    ),
                ]
            )

            if len(same_product_records) <= 1:
                record.classification_variance = 0.0
                continue

            # Calculate variance based on classification changes
            classifications = same_product_records.mapped("computed_level_id.name")
            unique_classifications = set(classifications)

            # Simple variance: number of different classifications
            record.classification_variance = len(unique_classifications) - 1

    @api.depends("percentage", "ranking")
    def _compute_season_performance(self):
        """Calculate performance indicator based on percentage and ranking."""
        for record in self:
            if record.percentage and record.ranking:
                # Performance score: higher percentage and lower ranking is better
                record.season_performance = (
                    record.percentage / max(record.ranking, 1) * 100
                )
            else:
                record.season_performance = 0.0

    @api.depends("classification_variance", "season_performance")
    def _compute_strategic_segment(self):
        """Categorize products based on classification variance and seasonal performance."""
        for record in self:
            variance = record.classification_variance or 0.0
            performance = record.season_performance or 0.0

            if variance >= 1 and performance > 15:
                record.strategic_segment = "seasonal_star"
            elif variance == 0 and performance > 10:
                record.strategic_segment = "business_pillar"
            elif variance >= 1 and 1 <= performance <= 10:
                record.strategic_segment = "seasonal_niche"
            else:
                record.strategic_segment = "marginal_product"
