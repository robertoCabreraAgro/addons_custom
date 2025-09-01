from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    """Inherit AccountAnalyticLine"""

    _inherit = "account.analytic.line"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    vehicle_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Asset",
        compute="_compute_asset_id",
        store=True,
        check_company=True,
        domain="[('asset_type', '=', 'vehicle')]",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("move_line_id.asset_id")
    def _compute_asset_id(self):
        for line in self:
            line.vehicle_id = line.move_line_id.asset_id
