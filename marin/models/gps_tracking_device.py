from odoo import api, fields, models


class GpsTrackingDevice(models.Model):
    """Extend GPS Tracking Device with department information"""

    _inherit = "gps.tracking.device"

    department_id = fields.Many2one(
        related="vehicle_id.department_id",
        store=True,
        string="Department",
    )

    @api.depends(
        "vehicle_id.driver_id", "vehicle_id.location", "vehicle_id.department_id"
    )
    def _compute_driver_name(self):
        """Override to include department dependency"""
        return super()._compute_driver_name()
