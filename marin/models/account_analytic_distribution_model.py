from odoo import fields, models


class AccountAnalyticDistributionModel(models.Model):
    """Inherit AccountAnalyticDistributionModel"""

    _inherit = "account.analytic.distribution.model"

    vehicle_id = fields.Many2one(
        "stock.lot",
        "Vehicle",
        domain="[('asset_type', '=', 'vehicle')]",
        ondelete="cascade",
        help="Select a vehicle for which the analytic distribution will be used (e.g. create new customer "
        "invoice or Sales order if we select this vehicle, it will automatically take this as an analytic account)",
    )
