from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GpsGeofenceType(models.Model):
    """Area type configuration for geofences with predefined colors and sequences."""
    
    _name = "gps.geofence.type"
    _description = "Geofence Area Type Configuration"
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string="Type Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, help="Technical code for area type")
    color = fields.Char(string="Hex Color", required=True, default="#808080", 
                       help="Default color for areas of this type")
    sequence = fields.Integer(string="Sequence", default=10, 
                             help="Default sequence for areas of this type")
    active = fields.Boolean(string="Active", default=True)
    description = fields.Text(string="Description")
    
    # Statistics
    geofence_count = fields.Integer(string="Areas Count", compute='_compute_geofence_count')
    
    @api.depends('code')
    def _compute_geofence_count(self):
        """Compute number of geofences using this type."""
        for record in self:
            record.geofence_count = self.env['gps.geofence'].search_count([
                ('area_type', '=', record.code)
            ])
    
    @api.constrains('code')
    def _check_unique_code(self):
        """Ensure area type codes are unique."""
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(f"Area type code '{record.code}' already exists.")
    
    @api.constrains('color')
    def _check_color_format(self):
        """Validate hex color format."""
        import re
        for record in self:
            if not re.match(r'^#[0-9A-Fa-f]{6}$', record.color):
                raise ValidationError(f"Invalid hex color format: {record.color}. Use format #RRGGBB")
    
    def action_view_geofences(self):
        """Action to view geofences of this type."""
        self.ensure_one()
        return {
            'name': f'Geographic Areas - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'gps.geofence',
            'view_mode': 'list,form',
            'domain': [('area_type', '=', self.code)],
            'context': {'default_area_type': self.code},
        }