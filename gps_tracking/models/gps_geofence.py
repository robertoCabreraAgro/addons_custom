import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GpsGeofence(models.Model):
    _name = "gps.geofence"
    _description = "Geographic Area Management"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'sequence, name'
    _parent_name = "parent_id"
    _parent_store = True

    name = fields.Char(string="Area Name", required=True, tracking=True)
    geometry = fields.GeoPolygon(string="Geographic Boundary", required=True)
    color = fields.Char(string="Hex Color", default=lambda self: self._get_default_color(), tracking=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    
    # New expanded fields
    sequence = fields.Integer(string="Sequence", default=lambda self: self._get_default_sequence())
    partner_id = fields.Many2one(
        'res.partner', 
        string="Client", 
        domain=[('customer_rank', '>', 0)],
        help="Client associated with this geographic area",
        tracking=True
    )
    area_type = fields.Selection([
        ('property', 'Property'),
        ('parcel', 'Parcel'),
        ('warehouse', 'Warehouse'), 
        ('corral', 'Corral'),
        ('cultivation_zone', 'Cultivation Zone'),
        ('other', 'Other')
    ], string="Area Type", required=True, default='property', tracking=True)
    
    parent_id = fields.Many2one(
        'gps.geofence',
        string="Parent Area", 
        help="Parent geographic area for hierarchical organization",
        tracking=True,
        index=True
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        'gps.geofence',
        'parent_id',
        string="Sub-areas"
    )
    
    main_entrance_point = fields.GeoPoint(
        string="Main Entrance Coordinates",
        help="GPS coordinates for the main entrance point"
    )
    
    description = fields.Text(string="Description")
    surface = fields.Float(string="Surface (m²)", help="Automatically calculated area in square meters using PostGIS", readonly=True)
    
    # Computed fields
    child_count = fields.Integer(string="Sub-areas Count", compute='_compute_child_count')
    full_name = fields.Char(string="Full Name", compute='_compute_full_name', store=True)
    
    def _get_default_color(self):
        """Get default color based on area_type or fallback."""
        if hasattr(self, '_context') and self._context.get('default_area_type'):
            area_type = self._context['default_area_type']
            geofence_type = self.env['gps.geofence.type'].search([
                ('code', '=', area_type)
            ], limit=1)
            if geofence_type:
                return geofence_type.color
        return '#FF0000'  # Default red
    
    def _get_default_sequence(self):
        """Get default sequence based on area_type or fallback."""
        if hasattr(self, '_context') and self._context.get('default_area_type'):
            area_type = self._context['default_area_type']
            geofence_type = self.env['gps.geofence.type'].search([
                ('code', '=', area_type)
            ], limit=1)
            if geofence_type:
                return geofence_type.sequence
        return 10  # Default sequence

    @api.depends('child_ids')
    def _compute_child_count(self):
        """Compute the number of child areas."""
        for record in self:
            record.child_count = len(record.child_ids)
    
    @api.depends('name', 'parent_id.name', 'area_type')
    def _compute_full_name(self):
        """Compute full hierarchical name."""
        for record in self:
            if record.parent_id:
                record.full_name = f"{record.parent_id.name} / {record.name}"
            else:
                record.full_name = record.name
    
    @api.depends('name', 'area_type', 'partner_id')
    def _compute_display_name(self):
        """Compute display name with area type and client."""
        for record in self:
            name_parts = [record.name]
            if record.area_type:
                area_type_label = dict(record._fields['area_type'].selection).get(record.area_type, '')
                name_parts.append(f"({area_type_label})")
            if record.partner_id:
                name_parts.append(f"- {record.partner_id.name}")
            record.display_name = " ".join(name_parts)
    
    @api.onchange('area_type')
    def _onchange_area_type(self):
        """Auto-assign color and sequence based on area type configuration."""
        if self.area_type:
            geofence_type = self.env['gps.geofence.type'].search([
                ('code', '=', self.area_type)
            ], limit=1)
            if geofence_type:
                self.color = geofence_type.color
                self.sequence = geofence_type.sequence
                return
            
        # If no area_type or no configuration found, set defaults
        if not self.area_type:
            self.color = '#808080'  # Default gray
            self.sequence = 10

    def _calculate_surface(self):
        """Calculate surface area using PostGIS ST_Area function."""
        if not self.geometry or not self.id:
            return 0.0
        
        try:
            # Check if PostGIS is available
            self.env.cr.execute("SELECT PostGIS_Version()")
            
            # Query surface directly from the database using the geometry field
            # Return area in square meters
            self.env.cr.execute("""
                SELECT ST_Area(ST_Transform(geometry, 3857)) as surface_m2
                FROM gps_geofence 
                WHERE id = %s AND geometry IS NOT NULL
            """, (self.id,))
            result = self.env.cr.fetchone()
            return float(result[0]) if result and result[0] else 0.0
        except Exception as e:
            _logger.warning(f"Error calculating surface for geofence {self.id}: {e}")
            return 0.0

    @api.model_create_multi  
    def create(self, vals_list):
        """Override create to calculate surface and apply type defaults on creation."""
        # Apply area type defaults before creation
        for vals in vals_list:
            if vals.get('area_type') and not vals.get('color') and not vals.get('sequence'):
                geofence_type = self.env['gps.geofence.type'].search([
                    ('code', '=', vals['area_type'])
                ], limit=1)
                if geofence_type:
                    vals.setdefault('color', geofence_type.color)
                    vals.setdefault('sequence', geofence_type.sequence)
        
        records = super().create(vals_list)
        
        # Calculate surface after the records are fully created (non-blocking)
        self.env.cr.commit()  # Ensure records are committed before surface calculation
        
        for record in records:
            if record.geometry and record.id:
                try:
                    surface_value = record._calculate_surface()
                    if surface_value and surface_value > 0:
                        # Update surface using SQL to avoid any ORM complications
                        record.env.cr.execute("""
                            UPDATE gps_geofence SET surface = %s WHERE id = %s
                        """, (surface_value, record.id))
                except Exception as e:
                    _logger.warning(f"Error calculating surface for new geofence {record.id}: {e}")
                    # Continue with creation even if surface calculation fails
        
        return records

    def write(self, vals):
        """Override write to recalculate surface when geometry changes."""
        result = super().write(vals)
        
        # Skip surface calculation if explicitly told to do so (prevents recursion)
        if self.env.context.get('skip_surface_calc'):
            return result
            
        if 'geometry' in vals:
            for record in self:
                if record.geometry and record.id:
                    try:
                        surface_value = record._calculate_surface()
                        if surface_value and surface_value > 0 and surface_value != record.surface:
                            # Update surface using SQL to avoid recursion
                            record.env.cr.execute("""
                                UPDATE gps_geofence SET surface = %s WHERE id = %s
                            """, (surface_value, record.id))
                            # Invalidate cache to reflect the change
                            record.invalidate_recordset(['surface'])
                    except Exception as e:
                        _logger.warning(f"Error updating surface for geofence {record.id}: {e}")
        return result

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        """Prevent recursive parent relationships."""
        if self._has_cycle():
            raise ValidationError("You cannot create recursive geographic area hierarchies.")
