from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    """Inherit AccountAnalyticLine"""

    _inherit = "account.analytic.line"

    vehicle_id = fields.Many2one(
        "stock.lot",
        "Vehicle",
        compute="_compute_vehicle_id",
        domain="[('asset_type', '=', 'vehicle')]",
        store=True,
        check_company=True,
    )

    @api.depends("move_line_id.asset_id")
    def _compute_vehicle_id(self):
        for line in self:
            line.vehicle_id = line.move_line_id.asset_id
