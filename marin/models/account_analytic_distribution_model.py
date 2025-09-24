from odoo import fields, models


class AccountAnalyticDistributionModel(models.Model):
    """Inherit AccountAnalyticDistributionModel"""

    _inherit = "account.analytic.distribution.model"

    asset_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Asset",
        ondelete="cascade",
        help="Select an asset for which the analytic distribution will be used (e.g. create new customer "
        "invoice or Sales order if we select this vehicle, it will automatically take this as an analytic account)",
    )
