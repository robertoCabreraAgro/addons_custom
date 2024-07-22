from odoo import fields, models


class Lead(models.Model):
    _inherit = "crm.lead"

    expected_area = fields.Float("Expected area", tracking=True)
    is_ag_initial = fields.Boolean("Initial AG lead", default=False)
    season_id = fields.Many2one(
        "date.range",
        "AG season",
        help="Since every farmer can have several growing seasons the specific one can be selected.",
    )
