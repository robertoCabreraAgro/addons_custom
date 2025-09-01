from odoo import api, models


class ResUsers(models.Model):
    """Extend res.users to provide GPS tracking permissions."""

    _inherit = "res.users"

    GPS_GROUP_MAPPING = [
        ("gps_tracking.group_gps_tracking_manager", "manager", True),
        ("gps_tracking.group_gps_tracking_private", "private", True),
        ("gps_tracking.group_gps_tracking_vehicle_loan", "vehicle_loan", False),
        ("gps_tracking.group_gps_tracking_reporting", "reporting", False),
        ("gps_tracking.group_gps_tracking_user", "user", False),
    ]

    # ------------------------------------------------------------
    # HEKLPERS
    # ------------------------------------------------------------

    @api.model
    def get_gps_tracking_permissions(self):
        """Get the GPS tracking permission level for the current user.

        Returns:
            dict: Contains 'group' (str) and 'can_read_private' (bool)
        """
        user = self.env.user

        # Check groups in priority order (highest to lowest privilege)
        for group_xml_id, group_name, can_read_private in self.GPS_GROUP_MAPPING:
            if user.has_group(group_xml_id):
                return {"group": group_name, "can_read_private": can_read_private}

        # Default: no access if not in any GPS tracking group
        return {"group": "none", "can_read_private": False}
