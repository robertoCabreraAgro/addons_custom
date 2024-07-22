from odoo import fields, models


class FleetVehicleLogServices(models.Model):
    _inherit = "fleet.vehicle.log.services"

    move_line_id = fields.Many2one("account.move.line", "Move Line")
