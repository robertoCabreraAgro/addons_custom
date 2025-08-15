import logging
import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Shapely and pyproj imports for geometric operations
try:
    from shapely.geometry import shape
    from shapely.ops import transform
    from pyproj import Transformer

    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

_logger = logging.getLogger(__name__)


class GpsGeofence(models.Model):
    _name = "gps.geofence"
    _description = "Geographic Area Management"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "sequence, name"
    _parent_name = "parent_id"
    _parent_store = True

    name = fields.Char(string="Area Name", required=True, tracking=True)
    geometry = fields.GeoPolygon(string="Geographic Boundary", required=True)
    color = fields.Char(
        string="Hex Color",
        default=lambda self: self._get_default_color(),
        tracking=True,
    )
    active = fields.Boolean(string="Active", default=True, tracking=True)

    # New expanded fields
    sequence = fields.Integer(
        string="Sequence", default=lambda self: self._get_default_sequence()
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Client",
        domain=["|", ("customer", "=", True), ("customer_rank", ">", 0)],
        help="Client associated with this geographic area",
        tracking=True,
    )
    area_type = fields.Selection(
        [
            ("property", "Property"),
            ("structure", "Structure"),
            ("parcel", "Parcel"),
            ("treatment", "Treatment"),
            ("demo_parcel", "Demo Parcel"),
        ],
        string="Area Type",
        required=True,
        default="property",
        tracking=True,
    )

    parent_id = fields.Many2one(
        "gps.geofence",
        string="Parent Area",
        help="Parent geographic area for hierarchical organization",
        tracking=True,
        index=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("gps.geofence", "parent_id", string="Sub-areas")

    main_entrance_point = fields.GeoPoint(
        string="Main Entrance Coordinates",
        help="GPS coordinates for the main entrance point",
    )

    description = fields.Text(string="Description")
    surface = fields.Float(
        string="Surface (ha)",
        help="Automatically calculated area in hectares",
        readonly=True,
        digits=(10, 4),
    )

    # Computed fields
    child_count = fields.Integer(
        string="Sub-areas Count", compute="_compute_child_count"
    )
    full_name = fields.Char(
        string="Full Name", compute="_compute_full_name", store=True
    )

    def _get_default_color(self):
        """Get default color based on area_type or fallback."""
        if hasattr(self, "_context") and self._context.get("default_area_type"):
            area_type = self._context["default_area_type"]
            geofence_type = self.env["gps.geofence.type"].search(
                [("code", "=", area_type)], limit=1
            )
            if geofence_type:
                return geofence_type.color
        return "#FF0000"  # Default red

    def _get_default_sequence(self):
        """Get default sequence based on area_type or fallback."""
        if hasattr(self, "_context") and self._context.get("default_area_type"):
            area_type = self._context["default_area_type"]
            geofence_type = self.env["gps.geofence.type"].search(
                [("code", "=", area_type)], limit=1
            )
            if geofence_type:
                return geofence_type.sequence
        return 10  # Default sequence

    @api.depends("child_ids")
    def _compute_child_count(self):
        """Compute the number of child areas."""
        for record in self:
            record.child_count = len(record.child_ids)

    @api.depends("name", "parent_id.name", "area_type")
    def _compute_full_name(self):
        """Compute full hierarchical name."""
        for record in self:
            if record.parent_id:
                record.full_name = f"{record.parent_id.name} / {record.name}"
            else:
                record.full_name = record.name

    @api.depends("name", "area_type", "partner_id")
    def _compute_display_name(self):
        """Compute display name with area type and client."""
        for record in self:
            name_parts = [record.name]
            if record.area_type:
                area_type_label = dict(record._fields["area_type"].selection).get(
                    record.area_type, ""
                )
                name_parts.append(f"({area_type_label})")
            if record.partner_id:
                name_parts.append(f"- {record.partner_id.name}")
            record.display_name = " ".join(name_parts)

    @api.onchange("area_type")
    def _onchange_area_type(self):
        """Auto-assign color and sequence based on area type configuration."""
        if self.area_type:
            # Validate hierarchy if there's a parent
            if self.parent_id and not self._validate_hierarchy(
                self.parent_id.area_type, self.area_type
            ):
                return {
                    "warning": {
                        "title": "Invalid Area Type",
                        "message": f'Area type "{self.area_type}" is not valid for parent "{self.parent_id.area_type}". '
                        f"Valid child types for {self.parent_id.area_type}: "
                        f'{", ".join(self._get_valid_children(self.parent_id.area_type))}',
                    }
                }

            # Validate hierarchy if there are children
            if self.child_ids:
                invalid_children = []
                for child in self.child_ids:
                    if not self._validate_hierarchy(self.area_type, child.area_type):
                        invalid_children.append(f"{child.name} ({child.area_type})")

                if invalid_children:
                    return {
                        "warning": {
                            "title": "Invalid Area Type Change",
                            "message": f'Cannot change to "{self.area_type}" because these child areas would become invalid:\n'
                            f'{", ".join(invalid_children)}\n\n'
                            f"Valid child types for {self.area_type}: "
                            f'{", ".join(self._get_valid_children(self.area_type))}',
                        }
                    }

            # Apply type configuration
            geofence_type = self.env["gps.geofence.type"].search(
                [("code", "=", self.area_type)], limit=1
            )
            if geofence_type:
                self.color = geofence_type.color
                self.sequence = geofence_type.sequence
                return

        # If no area_type or no configuration found, set defaults
        if not self.area_type:
            self.color = "#808080"  # Default gray
            self.sequence = 10

    def _calculate_surface(self):
        """Calculate surface area using WKT coordinates and convert to hectares."""
        if not self.geometry or not self.id:
            return 0.0

        try:
            # Method 1: Try using Shapely with WKT coordinates (most accurate)
            if SHAPELY_AVAILABLE:
                try:
                    surface_ha = self._calculate_surface_from_wkt()
                    if surface_ha and surface_ha > 0:
                        _logger.info(
                            f"✅ Surface calculated using WKT: {surface_ha:.4f} hectares"
                        )
                        return surface_ha
                except Exception as e:
                    _logger.warning(f"WKT surface calculation failed: {e}")

            # Method 2: Fallback to PostGIS (but convert to hectares)
            _logger.info("Using PostGIS fallback for surface calculation")
            self.env.cr.execute("SELECT PostGIS_Version()")

            # Get the original WKT and check if coordinates are in lat/lng
            self.env.cr.execute(
                """
                SELECT ST_AsText(geometry) as wkt
                FROM gps_geofence 
                WHERE id = %s AND geometry IS NOT NULL
            """,
                (self.id,),
            )

            wkt_result = self.env.cr.fetchone()
            if not wkt_result:
                return 0.0

            wkt = wkt_result[0]

            # Check if coordinates look like lat/lng (reasonable for Mexico)
            import re

            coord_pattern = r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)"
            matches = re.findall(coord_pattern, wkt)

            if matches:
                avg_lat = sum(float(match[1]) for match in matches) / len(matches)
                avg_lng = sum(float(match[0]) for match in matches) / len(matches)

                # If coordinates look like lat/lng, treat as EPSG:4326
                if 19.0 <= avg_lat <= 20.0 and -100.0 <= avg_lng <= -99.0:
                    _logger.info(
                        "Coordinates appear to be in lat/lng, using geography calculation"
                    )
                    # Use ST_Area with geography for accurate results in square meters
                    self.env.cr.execute(
                        """
                        SELECT ST_Area(ST_Transform(ST_SetSRID(geometry, 4326), 3857)) as surface_m2
                        FROM gps_geofence 
                        WHERE id = %s
                    """,
                        (self.id,),
                    )
                else:
                    # Use standard calculation
                    self.env.cr.execute(
                        """
                        SELECT ST_Area(ST_Transform(geometry, 3857)) as surface_m2
                        FROM gps_geofence 
                        WHERE id = %s
                    """,
                        (self.id,),
                    )
            else:
                # Standard calculation if no coordinates found
                self.env.cr.execute(
                    """
                    SELECT ST_Area(ST_Transform(geometry, 3857)) as surface_m2
                    FROM gps_geofence 
                    WHERE id = %s
                """,
                    (self.id,),
                )

            result = self.env.cr.fetchone()
            if result and result[0]:
                surface_m2 = float(result[0])
                surface_ha = surface_m2 / 10000  # Convert m² to hectares
                _logger.info(
                    f"✅ Surface calculated using PostGIS: {surface_ha:.4f} hectares ({surface_m2:.2f} m²)"
                )
                return surface_ha

            return 0.0

        except Exception as e:
            _logger.warning(f"Error calculating surface for geofence {self.id}: {e}")
            return 0.0

    def _calculate_surface_from_wkt(self):
        """Calculate surface area from WKT coordinates using Shapely (most accurate)."""
        try:
            # Get WKT coordinates
            self.env.cr.execute(
                """
                SELECT ST_AsText(geometry) as wkt
                FROM gps_geofence 
                WHERE id = %s
            """,
                (self.id,),
            )

            result = self.env.cr.fetchone()
            if not result:
                return 0.0

            wkt = result[0]

            # Extract coordinates using regex
            import re

            coord_pattern = r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)"
            matches = re.findall(coord_pattern, wkt)

            if not matches:
                return 0.0

            # Create GeoJSON from WKT coordinates
            coords = [[float(lng), float(lat)] for lng, lat in matches]

            # Ensure polygon is closed
            if coords[0] != coords[-1]:
                coords.append(coords[0])

            geojson = {"type": "Polygon", "coordinates": [coords]}

            # Create Shapely geometry in EPSG:4326 (lat/lng)
            geom_4326 = shape(geojson)

            # Transform to Web Mercator (EPSG:3857) for accurate area calculation
            geom_3857 = self._project_to_srid(geojson, from_srid=4326, to_srid=3857)

            if geom_3857:
                # Calculate area in square meters
                area_m2 = geom_3857.area
                # Convert to hectares
                area_ha = area_m2 / 10000

                _logger.info(f"📏 WKT Surface calculation:")
                _logger.info(f"   Coordinates: {len(coords)} points")
                _logger.info(f"   Area (m²): {area_m2:.2f}")
                _logger.info(f"   Area (ha): {area_ha:.4f}")

                return area_ha
            else:
                return 0.0

        except Exception as e:
            _logger.warning(f"Error in WKT surface calculation: {e}")
            return 0.0

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to calculate surface and apply type defaults on creation."""
        # Apply area type defaults before creation
        for vals in vals_list:
            if (
                vals.get("area_type")
                and not vals.get("color")
                and not vals.get("sequence")
            ):
                geofence_type = self.env["gps.geofence.type"].search(
                    [("code", "=", vals["area_type"])], limit=1
                )
                if geofence_type:
                    vals.setdefault("color", geofence_type.color)
                    vals.setdefault("sequence", geofence_type.sequence)

            # Log geometry information before creation
            if vals.get("geometry"):
                _logger.info(
                    f"📍 CREATE - Incoming geometry type: {type(vals['geometry'])}"
                )
                _logger.info(
                    f"📍 CREATE - Geometry preview: {str(vals['geometry'])[:200]}"
                )

        records = super().create(vals_list)

        # Calculate surface after the records are fully created (non-blocking)
        self.env.cr.commit()  # Ensure records are committed before surface calculation

        for record in records:
            if record.geometry and record.id:
                try:
                    surface_value = record._calculate_surface()
                    if surface_value and surface_value > 0:
                        # Update surface using SQL to avoid any ORM complications
                        record.env.cr.execute(
                            """
                            UPDATE gps_geofence SET surface = %s WHERE id = %s
                        """,
                            (surface_value, record.id),
                        )
                except Exception as e:
                    _logger.warning(
                        f"Error calculating surface for new geofence {record.id}: {e}"
                    )
                    # Continue with creation even if surface calculation fails

        return records

    def write(self, vals):
        """Override write to recalculate surface when geometry changes and validate area type changes."""
        # Validate area_type changes before writing
        if "area_type" in vals:
            for record in self:
                new_area_type = vals["area_type"]

                # Check parent hierarchy compatibility
                if record.parent_id and not record._validate_hierarchy(
                    record.parent_id.area_type, new_area_type
                ):
                    raise ValidationError(
                        f'Area type "{new_area_type}" is not valid for parent "{record.parent_id.area_type}" '
                        f'in geofence "{record.name}". '
                        f'Valid child types: {", ".join(record._get_valid_children(record.parent_id.area_type))}'
                    )

                # Check children hierarchy compatibility
                if record.child_ids:
                    invalid_children = []
                    for child in record.child_ids:
                        if not record._validate_hierarchy(
                            new_area_type, child.area_type
                        ):
                            invalid_children.append(f"{child.name} ({child.area_type})")

                    if invalid_children:
                        raise ValidationError(
                            f'Cannot change "{record.name}" to area type "{new_area_type}" because '
                            f'these child areas would become invalid: {", ".join(invalid_children)}. '
                            f'Valid child types for {new_area_type}: {", ".join(record._get_valid_children(new_area_type))}'
                        )

        result = super().write(vals)

        # Skip surface calculation if explicitly told to do so (prevents recursion)
        if self.env.context.get("skip_surface_calc"):
            return result

        if "geometry" in vals:
            for record in self:
                if record.geometry and record.id:
                    try:
                        surface_value = record._calculate_surface()
                        if (
                            surface_value
                            and surface_value > 0
                            and surface_value != record.surface
                        ):
                            # Update surface using SQL to avoid recursion
                            record.env.cr.execute(
                                """
                                UPDATE gps_geofence SET surface = %s WHERE id = %s
                            """,
                                (surface_value, record.id),
                            )
                            # Invalidate cache to reflect the change
                            record.invalidate_recordset(["surface"])
                    except Exception as e:
                        _logger.warning(
                            f"Error updating surface for geofence {record.id}: {e}"
                        )
        return result

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        """Prevent recursive parent relationships."""
        if self._has_cycle():
            raise ValidationError(
                "You cannot create recursive geographic area hierarchies."
            )

    @api.constrains("area_type", "parent_id")
    def _check_area_type_hierarchy(self):
        """Validate area type hierarchy on save."""
        for record in self:
            if record.parent_id and record.area_type:
                if not record._validate_hierarchy(
                    record.parent_id.area_type, record.area_type
                ):
                    raise ValidationError(
                        f'Area type "{record.area_type}" is not valid for parent "{record.parent_id.area_type}" '
                        f'in geofence "{record.name}". '
                        f'Valid child types: {", ".join(record._get_valid_children(record.parent_id.area_type))}'
                    )

    def _project_to_srid(self, geom_json, from_srid, to_srid):
        """
        Project GeoJSON geometry from one SRID to another using Shapely and pyproj.
        """
        if not SHAPELY_AVAILABLE:
            return None

        try:
            # Create shapely geometry from GeoJSON
            geom = shape(geom_json)

            # Skip transformation if SRIDs are the same
            if from_srid == to_srid:
                return geom

            # Create transformer for coordinate system conversion
            transformer = Transformer.from_crs(
                f"EPSG:{from_srid}", f"EPSG:{to_srid}", always_xy=True
            )

            # Transform geometry to target SRID
            projected_geom = transform(transformer.transform, geom)

            return projected_geom

        except Exception as e:
            _logger.warning(
                f"Error transforming geometry from {from_srid} to {to_srid}: {e}"
            )
            return None

    def _compare_geometries(self, container_geofence, new_geojson, new_srid=4326):
        """
        Compare new geometry with container geofence using Shapely and WKT coordinates.
        """
        if not SHAPELY_AVAILABLE:
            return None

        try:
            # Step 1: Get container geometry from WKT (avoiding transformation issues)
            self.env.cr.execute(
                """
                SELECT ST_AsText(geometry) as wkt
                FROM gps_geofence 
                WHERE id = %s
            """,
                (container_geofence.id,),
            )

            container_result = self.env.cr.fetchone()
            if not container_result or not container_result[0]:
                return None

            container_wkt = container_result[0]

            _logger.info(f"📍 WKT-BASED GEOMETRY COMPARISON:")
            _logger.info(f"   Using WKT coordinates directly")
            _logger.info(f"   Container WKT preview: {container_wkt[:100]}...")

            # Step 2: Extract coordinates from WKT and create GeoJSON
            import re

            coord_pattern = r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)"
            matches = re.findall(coord_pattern, container_wkt)

            if not matches:
                _logger.warning("No coordinates found in container WKT")
                return None

            # Create GeoJSON from WKT coordinates
            container_coords = [[float(lng), float(lat)] for lng, lat in matches]
            # Close the polygon if not already closed
            if container_coords[0] != container_coords[-1]:
                container_coords.append(container_coords[0])

            container_geojson = {"type": "Polygon", "coordinates": [container_coords]}

            # Step 3: Create Shapely geometries directly in lat/lng
            container_geom = shape(container_geojson)
            new_geom = shape(new_geojson)

            # Step 3: Extract bounds directly from coordinates
            container_bounds = (
                container_geom.bounds
            )  # (min_lng, min_lat, max_lng, max_lat)
            new_bounds = new_geom.bounds

            # Step 4: Bounds check (lng=x, lat=y)
            bounds_check = (
                container_bounds[0] <= new_bounds[0]  # min_lng
                and container_bounds[2] >= new_bounds[2]  # max_lng
                and container_bounds[1] <= new_bounds[1]  # min_lat
                and container_bounds[3] >= new_bounds[3]  # max_lat
            )

            _logger.info(f"   Container bounds (lng,lat,lng,lat): {container_bounds}")
            _logger.info(f"   New geometry bounds (lng,lat,lng,lat): {new_bounds}")
            _logger.info(f"   Bounds check: {bounds_check}")

            # Step 5: Spatial operations (only if bounds check passes)
            if bounds_check:
                contains_result = container_geom.contains(new_geom)
                covers_result = container_geom.covers(new_geom)
                intersects_result = container_geom.intersects(new_geom)

                _logger.info(f"   Contains: {contains_result}")
                _logger.info(f"   Covers: {covers_result}")
                _logger.info(f"   Intersects: {intersects_result}")

                return {
                    "contains": contains_result,
                    "covers": covers_result,
                    "intersects": intersects_result,
                    "bounds_check": bounds_check,
                    "container_bounds": container_bounds,
                    "target_bounds": new_bounds,
                }
            else:
                _logger.info("   Skipping spatial operations (bounds check failed)")
                return {
                    "contains": False,
                    "covers": False,
                    "intersects": False,
                    "bounds_check": bounds_check,
                    "container_bounds": container_bounds,
                    "target_bounds": new_bounds,
                }

        except Exception as e:
            _logger.warning(f"Error in simplified geometry comparison: {e}")
            import traceback

            _logger.warning(traceback.format_exc())
            return None

    def _calculate_intersection_percentage(self, container_geofence, new_geojson):
        """
        Calculate the percentage of new geometry that intersects with container.
        Returns percentage (0-100) or None if calculation fails.
        """
        if not SHAPELY_AVAILABLE:
            return None

        try:
            # Get container geometry from WKT
            self.env.cr.execute(
                """
                SELECT ST_AsText(geometry) as wkt
                FROM gps_geofence 
                WHERE id = %s
            """,
                (container_geofence.id,),
            )

            container_result = self.env.cr.fetchone()
            if not container_result or not container_result[0]:
                return None

            container_wkt = container_result[0]

            # Extract coordinates from WKT and create GeoJSON
            import re

            coord_pattern = r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)"
            matches = re.findall(coord_pattern, container_wkt)

            if not matches:
                return None

            # Create GeoJSON from WKT coordinates
            container_coords = [[float(lng), float(lat)] for lng, lat in matches]
            if container_coords[0] != container_coords[-1]:
                container_coords.append(container_coords[0])

            container_geojson = {"type": "Polygon", "coordinates": [container_coords]}

            # Create Shapely geometries
            container_geom = shape(container_geojson)
            new_geom = shape(new_geojson)

            # Calculate intersection
            intersection = container_geom.intersection(new_geom)

            # Calculate areas
            new_area = new_geom.area
            intersection_area = intersection.area

            if new_area > 0:
                percentage = (intersection_area / new_area) * 100
                _logger.info(f"📐 Intersection calculation:")
                _logger.info(f"   New polygon area: {new_area:.8f}")
                _logger.info(f"   Intersection area: {intersection_area:.8f}")
                _logger.info(f"   Intersection percentage: {percentage:.2f}%")
                return percentage
            else:
                return 0.0

        except Exception as e:
            _logger.warning(f"Error calculating intersection percentage: {e}")
            return None

    def _check_intersection_postgis_50_percent(self, new_geometry, container_geofence):
        """
        Check if at least 50% of new geometry intersects with container using PostGIS.
        """
        try:
            _logger.info(f"📍 POSTGIS 50% INTERSECTION ANALYSIS:")

            # Get container's SRID
            self.env.cr.execute(
                """
                SELECT ST_SRID(geometry) as container_srid
                FROM gps_geofence 
                WHERE id = %s
            """,
                (container_geofence.id,),
            )

            srid_result = self.env.cr.fetchone()
            if not srid_result:
                return False

            container_srid = srid_result[0]
            _logger.info(f"   Using container SRID: {container_srid}")

            # Calculate intersection percentage using PostGIS
            self.env.cr.execute(
                """
                WITH new_geom AS (
                    SELECT ST_Transform(
                        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 
                        %s
                    ) as geom
                )
                SELECT 
                    ST_Area(ST_Intersection(g.geometry, n.geom)) / NULLIF(ST_Area(n.geom), 0) * 100 as intersection_percentage,
                    ST_Intersects(g.geometry, n.geom) as intersects,
                    ST_Area(n.geom) as new_area,
                    ST_Area(ST_Intersection(g.geometry, n.geom)) as intersection_area
                FROM gps_geofence g, new_geom n
                WHERE g.id = %s
            """,
                (json.dumps(new_geometry), container_srid, container_geofence.id),
            )

            result = self.env.cr.fetchone()
            if result:
                intersection_percentage = float(result[0]) if result[0] else 0.0
                intersects = bool(result[1])
                new_area = float(result[2]) if result[2] else 0.0
                intersection_area = float(result[3]) if result[3] else 0.0

                _logger.info(f"   New polygon area: {new_area:.2f}")
                _logger.info(f"   Intersection area: {intersection_area:.2f}")
                _logger.info(
                    f"   Intersection percentage: {intersection_percentage:.2f}%"
                )
                _logger.info(
                    f"   Meets 50% requirement: {intersection_percentage >= 50.0}"
                )

                # Return True if at least 50% intersection
                return intersection_percentage >= 50.0

            return False

        except Exception as e:
            _logger.warning(f"Error in PostGIS 50% intersection check: {e}")
            import traceback

            _logger.warning(traceback.format_exc())
            return False

    def _check_containment_postgis_improved(self, new_geometry, container_geofence):
        """
        Improved PostGIS containment check using container's SRID.
        """
        try:
            _logger.info(f"📍 POSTGIS IMPROVED ANALYSIS:")

            # Step 1: Get container's SRID (this is our reference)
            self.env.cr.execute(
                """
                SELECT ST_SRID(geometry) as container_srid
                FROM gps_geofence 
                WHERE id = %s
            """,
                (container_geofence.id,),
            )

            srid_result = self.env.cr.fetchone()
            if not srid_result:
                return False

            container_srid = srid_result[0]
            _logger.info(f"   Using container SRID as reference: {container_srid}")

            # Step 2: Transform new geometry to container's SRID and compare
            # 🔥 KEY: Use container's SRID, not new geometry's SRID
            self.env.cr.execute(
                """
                WITH new_geom AS (
                    -- Set new geometry to EPSG:4326 (from frontend) then transform to container's SRID
                    SELECT ST_Transform(
                        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 
                        %s
                    ) as geom
                )
                SELECT 
                    ST_Covers(g.geometry, n.geom) as covers,
                    ST_Contains(g.geometry, n.geom) as contains,
                    ST_Intersects(g.geometry, n.geom) as intersects,
                    ST_AsText(ST_Envelope(g.geometry)) as container_envelope,
                    ST_AsText(ST_Envelope(n.geom)) as new_envelope
                FROM gps_geofence g, new_geom n
                WHERE g.id = %s
            """,
                (json.dumps(new_geometry), container_srid, container_geofence.id),
            )

            result = self.env.cr.fetchone()
            if result:
                covers_result = bool(result[0])
                contains_result = bool(result[1])
                intersects_result = bool(result[2])
                container_envelope = result[3]
                new_envelope = result[4]

                _logger.info(f"   Container envelope: {container_envelope}")
                _logger.info(f"   New geometry envelope: {new_envelope}")
                _logger.info(f"   ST_Intersects: {intersects_result}")
                _logger.info(f"   ST_Contains: {contains_result}")
                _logger.info(f"   ST_Covers: {covers_result}")

                # Use covers as primary (more tolerant)
                if covers_result:
                    return True
                elif intersects_result and contains_result:
                    # Intersects + contains = valid containment
                    return True
                else:
                    return False

            return False

        except Exception as e:
            _logger.warning(f"Error in improved PostGIS containment check: {e}")
            import traceback

            _logger.warning(traceback.format_exc())
            return False

    def _check_spatial_containment(self, new_geometry, container_geofence):
        """
        Check if the new geometry has at least 50% intersection with the container geofence.
        Modified to use 50% intersection instead of full containment.
        """
        if not container_geofence.geometry or not new_geometry:
            return False

        _logger.info(
            f"🔍 SPATIAL INTERSECTION CHECK (50%) - Container: {container_geofence.name} (ID: {container_geofence.id})"
        )

        # Method 1: New improved Shapely method (primary)
        if SHAPELY_AVAILABLE:
            _logger.info("📍 Using Shapely method for 50% intersection check")
            try:
                comparison_result = self._calculate_intersection_percentage(
                    container_geofence, new_geometry
                )

                if comparison_result is not None:
                    # Check if intersection is at least 50%
                    spatial_result = comparison_result >= 50.0
                    _logger.info(
                        f"✅ Intersection percentage: {comparison_result:.2f}%"
                    )
                    _logger.info(f"✅ Meets 50% requirement: {spatial_result}")
                    return spatial_result
                else:
                    _logger.warning("⚠️ Intersection calculation returned None")

            except Exception as e:
                _logger.warning(f"⚠️ Shapely intersection method failed: {e}")

        # Method 2: PostGIS fallback with 50% intersection
        _logger.info("📍 Using PostGIS method for 50% intersection (fallback)")
        try:
            result = self._check_intersection_postgis_50_percent(
                new_geometry, container_geofence
            )
            _logger.info(f"✅ PostGIS 50% intersection result: {result}")
            if result is not None:
                return result
        except Exception as e:
            _logger.warning(f"❌ PostGIS method also failed: {e}")

        # Final fallback - log detailed error information
        _logger.error(
            f"❌ ALL METHODS FAILED - Container: {container_geofence.name} (ID: {container_geofence.id})"
        )
        _logger.error(f"New geometry type: {new_geometry.get('type', 'Unknown')}")
        if "coordinates" in new_geometry:
            coords_preview = (
                new_geometry["coordinates"][0][:3]
                if new_geometry["coordinates"]
                else []
            )
            _logger.error(f"New geometry coordinates preview: {coords_preview}")

        return False

    def _get_valid_hierarchies(self):
        """
        Get the valid hierarchy mapping for area types.
        """
        return {
            "property": ["parcel", "structure", "demo_parcel"],
            "parcel": ["treatment"],
        }

    def _get_valid_children(self, area_type):
        """
        Get list of valid child area types for a given area type.
        """
        return self._get_valid_hierarchies().get(area_type, [])

    def _validate_hierarchy(self, container_area_type, new_area_type):
        """
        Validate if the new area type can be a child of the container area type.
        """
        allowed_children = self._get_valid_children(container_area_type)
        return new_area_type in allowed_children

    def _find_partner_in_hierarchy(self, container):
        """
        Find partner_id by searching up the hierarchy from the given container.
        Returns the first partner_id found, or False if none found.
        """
        current = container
        hierarchy_path = []

        while current:
            hierarchy_path.append(f"{current.name} ({current.area_type})")

            if current.partner_id:
                _logger.info(
                    f"📋 Partner found in hierarchy: {current.partner_id.name} at {current.name} ({current.area_type})"
                )
                _logger.info(f"📋 Hierarchy path: {' -> '.join(hierarchy_path)}")
                return current.partner_id.id

            # Subir un nivel en la jerarquía
            current = current.parent_id

        _logger.info(
            f"📋 No partner found in hierarchy path: {' -> '.join(hierarchy_path)}"
        )
        return False

    def _check_bounds_containment(self, new_bounds, container_bounds):
        """
        Check if the new bounds are completely contained within the container bounds.
        """

        contains = (
            container_bounds["min_lat"] <= new_bounds["min_lat"]
            and container_bounds["max_lat"] >= new_bounds["max_lat"]
            and container_bounds["min_lng"] <= new_bounds["min_lng"]
            and container_bounds["max_lng"] >= new_bounds["max_lng"]
        )

        _logger.info(f"📍 BOUNDS COMPARISON:")
        _logger.info(
            f"   Container Lat: [{container_bounds['min_lat']:.8f}, {container_bounds['max_lat']:.8f}]"
        )
        _logger.info(
            f"   New Poly  Lat: [{new_bounds['min_lat']:.8f}, {new_bounds['max_lat']:.8f}]"
        )
        _logger.info(
            f"   Container Lng: [{container_bounds['min_lng']:.8f}, {container_bounds['max_lng']:.8f}]"
        )
        _logger.info(
            f"   New Poly  Lng: [{new_bounds['min_lng']:.8f}, {new_bounds['max_lng']:.8f}]"
        )
        _logger.info(f"   Contains: {contains}")

        return contains

    def _find_container_geofence(self, geometry_geojson, area_type):
        """
        Find a container geofence that can contain the new geometry.
        """

        try:
            new_geom = (
                json.loads(geometry_geojson)
                if isinstance(geometry_geojson, str)
                else geometry_geojson
            )
            _logger.info(f"📍 Parsed geometry type: {new_geom.get('type', 'Unknown')}")

            if new_geom.get("coordinates") and len(new_geom["coordinates"]) > 0:
                coords = (
                    new_geom["coordinates"][0]
                    if new_geom["type"] == "Polygon"
                    else new_geom["coordinates"]
                )
                _logger.info(f"📍 Coordinates count: {len(coords) if coords else 0}")
                if coords and len(coords) > 0:
                    lats = [c[1] for c in coords]
                    lngs = [c[0] for c in coords]
                    _logger.info(
                        f"📍 Latitude range: [{min(lats):.8f}, {max(lats):.8f}]"
                    )
                    _logger.info(
                        f"📍 Longitude range: [{min(lngs):.8f}, {max(lngs):.8f}]"
                    )

                    # DETAILED POLYGON COORDINATES LOG
                    _logger.info("📍 BACKEND - NEW POLYGON COORDINATES (ALL POINTS):")
                    for i, coord in enumerate(coords):
                        _logger.info(
                            f"    Point {i+1}: [{coord[0]:.8f}, {coord[1]:.8f}]"
                        )

                    # Check if polygon is closed
                    is_closed = (
                        coords[0][0] == coords[-1][0] and coords[0][1] == coords[-1][1]
                    )
                    _logger.info(f"📍 Backend - Polygon is closed: {is_closed}")

                    # Calculate rough area using shoelace formula
                    area = 0
                    n = len(coords)
                    for i in range(n - 1):
                        area += coords[i][0] * coords[i + 1][1]
                        area -= coords[i + 1][0] * coords[i][1]
                    area = abs(area) / 2
                    _logger.info(
                        f"📍 Backend - Rough polygon area: {area:.8f} square degrees"
                    )
        except (json.JSONDecodeError, TypeError) as e:
            _logger.error(f"❌ Error parsing geometry: {e}")
            return {
                "parent_id": False,
                "partner_id": False,
                "validation_errors": ["Invalid geometry format"],
            }

        # Query all active geofences that can be containers, ordered by sequence (lower = higher priority)
        potential_containers = self.search(
            [
                ("active", "=", True),
                ("area_type", "in", ["property", "structure", "parcel"]),
            ],
            order="sequence, parent_path",
        )

        _logger.info(
            f"Found {len(potential_containers)} potential containers: {[f'{g.name}({g.area_type})' for g in potential_containers]}"
        )

        container_info = {
            "parent_id": False,
            "partner_id": False,
            "validation_errors": [],
        }

        # Extract bounds from new geometry for initial filtering
        new_bounds = {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lng": min(lngs),
            "max_lng": max(lngs),
        }

        # First pass: Filter by bounds comparison using direct coordinate extraction
        bounds_candidates = []
        for geofence in potential_containers:
            try:
                # SOLUTION: Extract coordinates directly from WKT (avoids SRID transformation issues)
                self.env.cr.execute(
                    """
                    SELECT 
                        ST_SRID(geometry) as original_srid,
                        ST_AsText(geometry) as wkt
                    FROM gps_geofence 
                    WHERE id = %s
                """,
                    (geofence.id,),
                )

                geom_result = self.env.cr.fetchone()
                if geom_result:
                    original_srid = geom_result[0]
                    wkt = geom_result[1]

                    _logger.info(f"\n🔍 EXTRACTING from WKT for: {geofence.name}")
                    _logger.info(f"   Original SRID: {original_srid}")
                    _logger.info(f"   WKT preview: {wkt[:100]}...")

                    # Extract coordinates directly from WKT using regex
                    # WKT format: POLYGON((-99.745237 19.256687,-99.742218 19.255747,...))
                    try:
                        import re

                        # Extract coordinate pairs from WKT
                        coord_pattern = r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)"
                        matches = re.findall(coord_pattern, wkt)

                        if matches:
                            # Convert to float coordinates (lng, lat)
                            container_coords = [
                                (float(lng), float(lat)) for lng, lat in matches
                            ]
                            container_lats = [coord[1] for coord in container_coords]
                            container_lngs = [coord[0] for coord in container_coords]

                            # VALIDATION: Check if coordinates make sense for Toluca area
                            avg_lat = sum(container_lats) / len(container_lats)
                            avg_lng = sum(container_lngs) / len(container_lngs)

                            _logger.info(f"   Extracted from WKT:")
                            _logger.info(f"     Count: {len(container_coords)}")
                            _logger.info(f"     Avg Lat: {avg_lat:.8f}")
                            _logger.info(f"     Avg Lng: {avg_lng:.8f}")
                            _logger.info(
                                f"     Lat range: [{min(container_lats):.8f}, {max(container_lats):.8f}]"
                            )
                            _logger.info(
                                f"     Lng range: [{min(container_lngs):.8f}, {max(container_lngs):.8f}]"
                            )

                            # Check if coordinates are reasonable for Mexico area
                            is_reasonable = (
                                19.0 <= avg_lat <= 20.0  # Toluca area latitude
                                and -101.0
                                <= avg_lng
                                <= -99.0  # Toluca area longitude (expanded range)
                            )

                            if is_reasonable:
                                _logger.info(
                                    f"   ✅ WKT coordinates look correct for Toluca area"
                                )

                                container_bounds = {
                                    "min_lat": min(container_lats),
                                    "max_lat": max(container_lats),
                                    "min_lng": min(container_lngs),
                                    "max_lng": max(container_lngs),
                                }

                                if self._check_bounds_containment(
                                    new_bounds, container_bounds
                                ):
                                    bounds_candidates.append(geofence)
                                    _logger.info(
                                        f"✅ {geofence.name} passes bounds check"
                                    )
                                else:
                                    _logger.info(
                                        f"❌ {geofence.name} fails bounds check"
                                    )
                            else:
                                _logger.warning(
                                    f"   ❌ WKT coordinates look incorrect for {geofence.name}"
                                )
                                _logger.warning(
                                    f"   Expected: Lat ~19.25, Lng ~-99.75 for Toluca"
                                )

                        else:
                            _logger.warning(
                                f"No coordinate matches found in WKT for {geofence.name}"
                            )

                    except Exception as e:
                        _logger.error(f"Error parsing WKT for {geofence.name}: {e}")

            except Exception as e:
                _logger.warning(f"Error getting bounds for geofence {geofence.id}: {e}")
                continue

        _logger.info(
            f"\n📊 Bounds filtering: {len(potential_containers)} → {len(bounds_candidates)} candidates"
        )

        # Second pass: 50% intersection check only on bounds candidates
        spatial_containers = []
        for geofence in bounds_candidates:
            if self._check_spatial_containment(new_geom, geofence):
                spatial_containers.append(geofence)
                _logger.info(
                    f"✅ 50% intersection confirmed: {geofence.name} ({geofence.area_type})"
                )

        _logger.info(
            f"📊 50% intersection filtering: {len(bounds_candidates)} → {len(spatial_containers)} containers"
        )

        if not spatial_containers:
            _logger.info("No containers with 50% intersection found")
            return container_info

        # Find the most immediate container (lowest sequence = higher priority, then smallest area)
        immediate_container = None
        best_sequence = float("inf")
        min_surface = float("inf")

        # First filter by valid hierarchy, then find the most immediate container
        valid_containers = []
        for container in spatial_containers:
            if self._validate_hierarchy(container.area_type, area_type):
                valid_containers.append(container)

        if not valid_containers:
            container_info["validation_errors"].append(
                f"No valid containers found for {area_type}"
            )
            return container_info

        # Now find the best container among the hierarchically valid ones
        for container in valid_containers:
            # Calculate container surface if not already calculated
            container_surface = container.surface
            if not container_surface:
                container_surface = container._calculate_surface()

            _logger.info(
                f"📋 Evaluating container: {container.name} ({container.area_type})"
            )
            _logger.info(
                f"   - Sequence: {container.sequence}, Surface: {container_surface}"
            )
            _logger.info(
                f"   - Has partner_id: {bool(container.partner_id)} - {container.partner_id.name if container.partner_id else 'None'}"
            )

            # Priority: sequence (lower is better), then surface (smaller is better)
            if container.sequence < best_sequence or (
                container.sequence == best_sequence and container_surface < min_surface
            ):
                immediate_container = container
                best_sequence = container.sequence
                min_surface = container_surface
                _logger.info(f"   - ✅ NEW BEST CONTAINER selected")

        if immediate_container:
            container_info["parent_id"] = immediate_container.id

            # Buscar partner_id en la jerarquía hacia arriba
            partner_id = self._find_partner_in_hierarchy(immediate_container)
            container_info["partner_id"] = partner_id

            _logger.info(
                f"✅ Selected container: {immediate_container.name} ({immediate_container.area_type})"
            )
            _logger.info(
                f"✅ Container partner_id: {immediate_container.partner_id.id if immediate_container.partner_id else 'None'}"
            )
            _logger.info(f"✅ Partner found in hierarchy: {partner_id}")
            _logger.info(f"✅ Container info returned: {container_info}")

        return container_info

    @api.model
    def find_container_for_geometry(self, geometry_geojson, area_type="property"):
        """
        Find a container geofence for the given geometry.
        """
        return self._find_container_geofence(geometry_geojson, area_type)

    def detect_and_update_container(self):
        """
        Post-create method to detect and update container geofence.
        """
        self.ensure_one()

        _logger.info(
            f"🔄 POST-CREATE CONTAINER DETECTION for {self.name} (ID: {self.id})"
        )

        if not self.geometry:
            return {"success": False, "message": "No geometry defined"}

        try:
            # Get geometry as GeoJSON for detection
            self.env.cr.execute(
                """
                SELECT ST_AsGeoJSON(geometry) as geojson
                FROM gps_geofence 
                WHERE id = %s
            """,
                (self.id,),
            )

            result = self.env.cr.fetchone()
            if not result or not result[0]:
                return {"success": False, "message": "Could not retrieve geometry"}

            geometry_geojson = result[0]

            # Find container using our detection method
            container_info = self._find_container_geofence(
                geometry_geojson, self.area_type
            )

            # Update fields if container found
            update_vals = {}
            if container_info.get("parent_id"):
                update_vals["parent_id"] = container_info["parent_id"]

            if container_info.get("partner_id") and not self.partner_id:
                # Only update partner if not already set
                update_vals["partner_id"] = container_info["partner_id"]
                _logger.info(
                    f"📋 Will inherit partner_id: {container_info['partner_id']}"
                )
            else:
                _logger.info(
                    f"📋 Partner inheritance skipped - container partner: {container_info.get('partner_id')}, current partner: {self.partner_id}"
                )

            if update_vals:
                _logger.info(f"✅ Updating geofence {self.id} with: {update_vals}")
                self.with_context(skip_container_detection=True).write(update_vals)

                return {
                    "success": True,
                    "parent_id": update_vals.get("parent_id"),
                    "partner_id": update_vals.get("partner_id"),
                    "message": "Container detected and fields updated",
                }
            else:
                return {
                    "success": True,
                    "message": "No container found or no updates needed",
                }

        except Exception as e:
            _logger.error(f"❌ Error in post-create container detection: {e}")
            import traceback

            _logger.error(traceback.format_exc())
            return {"success": False, "message": f"Error detecting container: {str(e)}"}

    @api.model
    def create_and_detect_container(self, vals):
        """
        Create a new geofence and detect its container in one step.
        """
        try:
            # Step 1: Create the geofence without container detection
            _logger.info("📍 STEP 1: Creating geofence without container detection")
            record = self.with_context(skip_container_detection=True).create(vals)

            # Step 2: Detect and update container
            _logger.info("📍 STEP 2: Detecting container and updating fields")
            detection_result = record.detect_and_update_container()

            return {
                "id": record.id,
                "success": True,
                "detection_result": detection_result,
            }

        except Exception as e:
            _logger.error(f"❌ Error in create_and_detect_container: {e}")
            return {"success": False, "error": str(e)}

    def action_view_in_dashboard(self):
        """
        Redirect to GPS Dashboard with this geofence's coordinates.
        """
        self.ensure_one()

        if not self.main_entrance_point:
            # If no main entrance point, try to calculate it from geometry
            if self.geometry:
                try:
                    # Get centroid of the geometry as fallback
                    self.env.cr.execute(
                        """
                        SELECT ST_Y(ST_Centroid(geometry)) as lat, ST_X(ST_Centroid(geometry)) as lng
                        FROM gps_geofence 
                        WHERE id = %s
                    """,
                        (self.id,),
                    )

                    result = self.env.cr.fetchone()
                    if result:
                        lat, lng = result
                        context = {
                            "default_center_lat": lat,
                            "default_center_lng": lng,
                            "default_zoom": 20,
                            "geofence_id": self.id,
                            "geofence_name": self.name,
                        }
                    else:
                        context = {}
                except Exception as e:
                    _logger.warning(f"Error getting geometry centroid: {e}")
                    context = {}
            else:
                context = {}
        else:
            # Extract coordinates from main_entrance_point (PostGIS Point)
            try:
                self.env.cr.execute(
                    """
                    SELECT ST_Y(main_entrance_point) as lat, ST_X(main_entrance_point) as lng
                    FROM gps_geofence 
                    WHERE id = %s
                """,
                    (self.id,),
                )

                result = self.env.cr.fetchone()
                if result:
                    lat, lng = result
                    context = {
                        "default_center_lat": lat,
                        "default_center_lng": lng,
                        "default_zoom": 20,
                        "geofence_id": self.id,
                        "geofence_name": self.name,
                    }
                else:
                    context = {}
            except Exception as e:
                _logger.warning(
                    f"Error extracting coordinates from main_entrance_point: {e}"
                )
                context = {}

        return {
            "type": "ir.actions.client",
            "name": f"GPS Dashboard - {self.name}",
            "tag": "gps_tracking_client_action",
            "target": "current",
            "context": context,
            "params": {
                "searchViewId": self.env.ref(
                    "gps_tracking.view_gps_tracking_device_search"
                ).id,
                "context": context,
            },
        }

    @api.model
    def calculate_geometry_surface(self, geometry_geojson):
        """
        Calculate the surface area of a geometry in hectares.
        """
        if not geometry_geojson:
            return 0.0

        try:
            # Method 1: Use Shapely for accurate calculation
            if SHAPELY_AVAILABLE:
                try:
                    geometry_dict = (
                        json.loads(geometry_geojson)
                        if isinstance(geometry_geojson, str)
                        else geometry_geojson
                    )

                    # Create Shapely geometry in EPSG:4326 (assuming GeoJSON is in lat/lng)
                    geom_4326 = shape(geometry_dict)

                    # Transform to Web Mercator (EPSG:3857) for accurate area calculation
                    geom_3857 = self._project_to_srid(
                        geometry_dict, from_srid=4326, to_srid=3857
                    )

                    if geom_3857:
                        # Calculate area in square meters, then convert to hectares
                        area_m2 = geom_3857.area
                        area_ha = area_m2 / 10000

                        _logger.info(f"📏 Geometry surface calculation:")
                        _logger.info(f"   Area (m²): {area_m2:.2f}")
                        _logger.info(f"   Area (ha): {area_ha:.4f}")

                        return area_ha

                except Exception as e:
                    _logger.warning(f"Shapely surface calculation failed: {e}")

            # Method 2: Fallback to PostGIS
            geometry_dict = (
                json.loads(geometry_geojson)
                if isinstance(geometry_geojson, str)
                else geometry_geojson
            )

            # Check if PostGIS is available
            self.env.cr.execute("SELECT PostGIS_Version()")

            # Calculate surface area using PostGIS, assuming input is in EPSG:4326
            self.env.cr.execute(
                """
                SELECT ST_Area(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 3857)) as surface_m2
            """,
                (json.dumps(geometry_dict),),
            )

            result = self.env.cr.fetchone()
            if result and result[0]:
                surface_m2 = float(result[0])
                surface_ha = surface_m2 / 10000  # Convert to hectares
                _logger.info(
                    f"📏 PostGIS surface calculation: {surface_ha:.4f} hectares"
                )
                return surface_ha

            return 0.0

        except Exception as e:
            _logger.warning(f"Error calculating geometry surface: {e}")
            return 0.0
