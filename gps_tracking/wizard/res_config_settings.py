from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    inactivity_threshold_hours = fields.Float(
        default=2,
        config_parameter="gps_tracking.inactivity_threshold_hours",
    )
    inactivity_warning = fields.Boolean(
        default=True,
        config_parameter="gps_tracking.inactivity_warning_enabled",
    )
    inactivity_warning_hours = fields.Float(
        default=1.5,
        config_parameter="gps_tracking.inactivity_warning_hours",
    )
