from odoo import api, fields, models, _


class IotBox(models.Model):
    _inherit = "iot.box"

    is_gps_virtual_box = fields.Boolean(
        string="GPS Virtual Box",
        compute="_compute_is_gps_virtual_box",
        help="This is a virtual IoT box for GPS devices",
    )

    gps_device_count = fields.Integer(
        string="GPS Devices",
        compute="_compute_gps_device_count",
        help="Number of GPS tracking devices connected",
    )

    @api.depends("identifier")
    def _compute_is_gps_virtual_box(self):
        for box in self:
            box.is_gps_virtual_box = box.identifier == "gps_virtual_box"

    @api.depends("device_ids.type")
    def _compute_gps_device_count(self):
        for box in self:
            box.gps_device_count = len(
                box.device_ids.filtered(lambda d: d.type == "gps_tracker")
            )

    def action_view_gps_devices(self):
        """View GPS devices connected to this box"""
        self.ensure_one()
        return {
            "name": _("GPS Devices"),
            "type": "ir.actions.act_window",
            "res_model": "iot.device",
            "view_mode": "tree,form",
            "domain": [("iot_id", "=", self.id), ("type", "=", "gps_tracker")],
            "context": {
                "default_iot_id": self.id,
                "default_type": "gps_tracker",
                "default_connection": "network",
            },
        }

    @api.model
    def get_or_create_gps_virtual_box(self):
        """Get or create the virtual IoT box for GPS devices

        :return: GPS virtual box record
        """
        gps_box = self.search([("identifier", "=", "gps_virtual_box")], limit=1)

        if not gps_box:
            gps_box = self.create(
                {
                    "name": "GPS Virtual Box",
                    "identifier": "gps_virtual_box",
                    "ip": "virtual.gps.local",
                    "version": "1.0",
                    "drivers_auto_update": False,  # Virtual box doesn't need driver updates
                }
            )

        return gps_box
