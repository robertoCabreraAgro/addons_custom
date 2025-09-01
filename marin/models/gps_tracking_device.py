from odoo import api, fields, models


class GpsTrackingDevice(models.Model):
    """Extend GPS Tracking Device with department information"""

    _inherit = "gps.tracking.device"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    department_id = fields.Many2one(
        comodel_name="hr.department",
        compute="_compute_asset_info",
        store=True,
        readonly=True,
    )
    driver_name = fields.Char(
        compute="_compute_asset_info",
        store=True,
        readonly=True,
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("asset_ids")
    def _compute_asset_info(self):
        """Compute asset related information"""
        for device in self:
            if device.asset_ids:
                asset = device.asset_ids[0]
                device.department_id = asset.operator_id.department_id
                device.driver_name = asset.operator_id.name
            else:
                device.department_id = False
                device.driver_name = False
