import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GpsGeofenceType(models.Model):
    """Area type configuration for geofences with predefined colors and sequences."""

    _name = "gps.geofence.type"
    _description = "Geofence Area Type Configuration"
    _order = "sequence, name"
    _rec_name = "name"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    name = fields.Char(string="Type Name", required=True, translate=True)
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Default sequence for areas of this type",
    )
    code = fields.Char(
        string="Code",
        required=True,
        help="Technical code for area type",
    )
    color = fields.Char(
        string="Hex Color",
        required=True,
        default="#808080",
        help="Default color for areas of this type",
    )
    description = fields.Text(string="Description")
    count_geofence = fields.Integer(
        string="Areas Count",
        compute="_compute_count_geofence",
    )

    # ------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------

    _unique_code = models.Constraint(
        "unique (code)",
        "This code already exists",
    )

    @api.constrains("color")
    def _check_color_format(self):
        """Validate hex color format."""
        for record in self:
            if not re.match(r"^#[0-9A-Fa-f]{6}$", record.color):
                raise ValidationError(
                    f"Invalid hex color format: {record.color}. Use format #RRGGBB"
                )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_count_geofence(self):
        """Compute number of geofences using this type."""
        for record in self:
            record.count_geofence = self.env["gps.geofence"].search_count(
                [("area_type", "=", record.code)]
            )

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_view_geofences(self):
        """Action to view geofences of this type."""
        self.ensure_one()
        return {
            "name": f"Geographic Areas - {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "gps.geofence",
            "view_mode": "list,form",
            "domain": [("area_type", "=", self.code)],
            "context": {"default_area_type": self.code},
        }
