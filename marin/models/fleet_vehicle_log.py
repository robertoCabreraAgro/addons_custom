from odoo import fields, models


class FleetVehiclelog(models.Model):
    _inherit = "fleet.vehicle.log"

    approval_request_id = fields.Many2one(
        comodel_name="approval.request",
    )
