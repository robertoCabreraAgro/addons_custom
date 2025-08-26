from odoo import api, fields, models


class GpsTrackingDevice(models.Model):
    """Extend GPS Tracking Device with department information"""

    _inherit = "gps.tracking.device"

    department_id = fields.Many2one(
        related="vehicle_id.department_id",
        store=True,
        string="Department",
    )
    driver_name = fields.Char(
        related="vehicle_id.driver_id.name",
        store=True,
        string="Driver",
        readonly=True,
    )
