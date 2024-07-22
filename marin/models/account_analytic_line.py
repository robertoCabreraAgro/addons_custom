from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    vehicle_id = fields.Many2one(
        "fleet.vehicle", "Vehicle", compute="_compute_vehicle_id", store=True, check_company=True
    )

    @api.depends("move_line_id.vehicle_id")
    def _compute_vehicle_id(self):
        for line in self:
            line.vehicle_id = line.move_line_id.vehicle_id
