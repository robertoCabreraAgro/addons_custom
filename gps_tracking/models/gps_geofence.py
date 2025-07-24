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
    color = fields.Char(string="Hex Color", default="#FF0000", tracking=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    
    # New expanded fields
    sequence = fields.Integer(string="Sequence", default=10)
    partner_id = fields.Many2one(
        'res.partner', 
        string="Client", 
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
    area_size = fields.Float(string="Area Size (hectares)", help="Calculated area in hectares")
    
    # Computed fields
    child_count = fields.Integer(string="Sub-areas Count", compute='_compute_child_count')
    full_name = fields.Char(string="Full Name", compute='_compute_full_name', store=True)
    
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
    
    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        """Prevent recursive parent relationships."""
        if self._has_cycle():
            raise ValidationError("You cannot create recursive geographic area hierarchies.")
