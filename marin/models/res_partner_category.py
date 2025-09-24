from odoo import fields, models


class ResPartnerCategory(models.Model):
    """Extends res.partner.category with dynamic scoring functionality.

    This extension allows configuring score values and activation flags for
    each partner category, enabling dynamic client classification based on
    configurable scoring instead of hardcoded values.
    """

    _inherit = "res.partner.category"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    score_value = fields.Float(
        string="Score Value",
        default=0.0,
        help="Score value for this category when calculating partner classification",
    )

    scoring_active = fields.Boolean(
        string="Include in Scoring",
        default=False,
        help="If checked, this category will be included in partner scoring calculations",
    )
