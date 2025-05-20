from odoo import fields, models


class FleetVehiclelog(models.Model):
    """Inherit FleetVehiclelog"""

    _inherit = "fleet.vehicle.log"

    approval_request_id = fields.Many2one(
        comodel_name="approval.request",
    )
    qty_fuel = fields.Float(
        string="Fuel Quantity (Liters)",
        help="Quantity of fuel added to the vehicle",
    )
    efficiency = fields.Float(
        string="Efficiency (km/L)",
        aggregator="avg",
        help="Fuel efficiency in kilometers per liter",
    )

    def action_open_upload_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Importar Logs",
            "res_model": "fleet.vehicle.log.import",
            "view_mode": "form",
            "target": "new",
        }
