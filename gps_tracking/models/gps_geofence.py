import json
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

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
    _rec_name = "name"
    _order = "sequence, name"
    _parent_name = "parent_id"
    _parent_store = True

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    name = fields.Char(string="Area Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(
        string="Sequence",
        default=lambda self: self._get_default_sequence(),
    )
    geometry = fields.GeoPolygon(string="Geographic Boundary", required=True)
    area_type = fields.Selection(
        selection=[
            ("property", "Property"),
            ("structure", "Structure"),
            ("parcel", "Parcel"),
            ("treatment", "Treatment"),
            ("demo_parcel", "Demo Parcel"),
        ],
        string="Area Type",
        required=True,
        default="property",
    )
    parent_id = fields.Many2one(
        comodel_name="gps.geofence",
        string="Parent Area",
        index=True,
        help="Parent geographic area for hierarchical organization",
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("gps.geofence", "parent_id", string="Sub-areas")
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Client",
        domain=["|", ("customer", "=", True), ("customer_rank", ">", 0)],
        help="Client associated with this geographic area",
    )
    color = fields.Char(
        string="Hex Color",
        default=lambda self: self._get_default_color(),
    )
    description = fields.Text(string="Description")
    main_entrance_point = fields.GeoPoint(
        string="Main Entrance Point",
        help="GPS coordinates for the main entrance point",
    )
    surface = fields.Float(
        string="Surface (ha)",
        digits=(10, 4),
        readonly=True,
        help="Automatically calculated area in hectares",
    )
    geometry_area = fields.Float(
        string="Area (ha)",
        digits=(10, 4),
        compute="_compute_geometry_area",
        store=True,
        readonly=True,
        help="Geometry calculated area in hectares",
    )
    count_child_ids = fields.Integer(
        string="Sub-areas Count",
        compute="_compute_count_child_ids",
    )

    # ------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to apply type defaults on creation."""
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

        return super().create(vals_list)

    def write(self, vals):
        """Override write to validate area type changes."""
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

        return super().write(vals)

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("child_ids")
    def _compute_count_child_ids(self):
        """Compute the number of child areas."""
        for record in self:
            record.count_child_ids = len(record.child_ids)

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

    @api.depends("geometry")
    def _compute_geometry_area(self):
        """Compute display name with area type and client."""
        for record in self:
            if record.geometry:
                record.geometry_area = record._calculate_surface()
            else:
                record.geometry_area = 0.0

    # ------------------------------------------------------------
    # ONCHANGE METHODS
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

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
                return surface_ha

            return 0.0

        except Exception as e:
            return 0.0

    def _calculate_surface_from_wkt(self):
        """Calculate surface area from WKT coordinates using Shapely (most accurate)."""
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

        # Transform to Web Mercator (EPSG:3857) for accurate area calculation
        geom_3857 = self._project_to_srid(geojson, from_srid=4326, to_srid=3857)

        if geom_3857:
            area_ha = geom_3857.area / 10000
            return area_ha
        else:
            return 0.0

    def _project_to_srid(self, geom_json, from_srid, to_srid):
        """
        Project GeoJSON geometry from one SRID to another using Shapely and pyproj.
        """
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

    def _compare_geometries(self, container_geofence, new_geojson, new_srid=4326):
        """
        Compare new geometry with container geofence using Shapely and WKT coordinates.
        """
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

            # Step 2: Extract coordinates from WKT and create GeoJSON
            coord_pattern = r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)"
            matches = re.findall(coord_pattern, container_wkt)

            if not matches:
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

            # Step 5: Spatial operations (only if bounds check passes)
            if bounds_check:
                contains_result = container_geom.contains(new_geom)
                covers_result = container_geom.covers(new_geom)
                intersects_result = container_geom.intersects(new_geom)

                return {
                    "contains": contains_result,
                    "covers": covers_result,
                    "intersects": intersects_result,
                    "bounds_check": bounds_check,
                    "container_bounds": container_bounds,
                    "target_bounds": new_bounds,
                }
            else:
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
            return None

    def _calculate_intersection_percentage(self, container_geofence, new_geojson):
        """
        Calculate the percentage of new geometry that intersects with container.
        Returns percentage (0-100) or None if calculation fails.
        """
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
                return percentage
            else:
                return 0.0

        except Exception as e:
            return None

    def _check_intersection_postgis_50_percent(self, new_geometry, container_geofence):
        """
        Check if at least 50% of new geometry intersects with container using PostGIS.
        """
        try:
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

                # Return True if at least 50% intersection
                return intersection_percentage >= 50.0

            return False

        except Exception as e:
            _logger.warning(f"Error in PostGIS 50% intersection check: {e}")
            return False

    def _check_containment_postgis_improved(self, new_geometry, container_geofence):
        """
        Improved PostGIS containment check using container's SRID.
        """
        try:
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
            return False

    def _check_spatial_containment(self, new_geometry, container_geofence):
        """
        Check if the new geometry has at least 50% intersection with the container geofence.
        Modified to use 50% intersection instead of full containment.
        """
        if not container_geofence.geometry or not new_geometry:
            return False

        # Method 1: New improved Shapely method (primary)
        if SHAPELY_AVAILABLE:
            try:
                comparison_result = self._calculate_intersection_percentage(
                    container_geofence, new_geometry
                )

                if comparison_result is not None:
                    # Check if intersection is at least 50%
                    spatial_result = comparison_result >= 50.0
                    return spatial_result
                else:
                    _logger.warning("⚠️ Intersection calculation returned None")

            except Exception as e:
                _logger.warning(f"⚠️ Shapely intersection method failed: {e}")

        try:
            result = self._check_intersection_postgis_50_percent(
                new_geometry, container_geofence
            )
            if result is not None:
                return result
        except Exception as e:
            _logger.warning(f"❌ PostGIS method also failed: {e}")

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
                return current.partner_id.id

            # Subir un nivel en la jerarquía
            current = current.parent_id
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

            if new_geom.get("coordinates") and len(new_geom["coordinates"]) > 0:
                coords = (
                    new_geom["coordinates"][0]
                    if new_geom["type"] == "Polygon"
                    else new_geom["coordinates"]
                )
                if coords and len(coords) > 0:
                    lats = [c[1] for c in coords]
                    lngs = [c[0] for c in coords]

                    # DETAILED POLYGON COORDINATES LOG
                    # Check if polygon is closed
                    is_closed = (
                        coords[0][0] == coords[-1][0] and coords[0][1] == coords[-1][1]
                    )

                    # Calculate rough area using shoelace formula
                    area = 0
                    n = len(coords)
                    for i in range(n - 1):
                        area += coords[i][0] * coords[i + 1][1]
                        area -= coords[i + 1][0] * coords[i][1]
                    area = abs(area) / 2
        except (json.JSONDecodeError, TypeError) as e:
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
                    wkt = geom_result[1]

                    # Extract coordinates directly from WKT using regex
                    # WKT format: POLYGON((-99.745237 19.256687,-99.742218 19.255747,...))
                    try:
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

                            # Check if coordinates are reasonable for Mexico area
                            is_reasonable = (
                                19.0 <= avg_lat <= 20.0  # Toluca area latitude
                                and -101.0
                                <= avg_lng
                                <= -99.0  # Toluca area longitude (expanded range)
                            )

                            if is_reasonable:
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
                continue

        # Second pass: 50% intersection check only on bounds candidates
        spatial_containers = []
        for geofence in bounds_candidates:
            if self._check_spatial_containment(new_geom, geofence):
                spatial_containers.append(geofence)


        if not spatial_containers:
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

            # Priority: sequence (lower is better), then surface (smaller is better)
            if container.sequence < best_sequence or (
                container.sequence == best_sequence and container_surface < min_surface
            ):
                immediate_container = container
                best_sequence = container.sequence
                min_surface = container_surface

        if immediate_container:
            container_info["parent_id"] = immediate_container.id

            # Buscar partner_id en la jerarquía hacia arriba
            partner_id = self._find_partner_in_hierarchy(immediate_container)
            container_info["partner_id"] = partner_id

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
            else:
                _logger.info(
                    f"📋 Partner inheritance skipped - container partner: {container_info.get('partner_id')}, current partner: {self.partner_id}"
                )

            if update_vals:
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
            return {"success": False, "message": f"Error detecting container: {str(e)}"}

    @api.model
    def create_and_detect_container(self, vals):
        """
        Create a new geofence and detect its container in one step.
        """
        try:
            # Step 1: Create the geofence without container detection
            record = self.with_context(skip_container_detection=True).create(vals)

            # Step 2: Detect and update container
            detection_result = record.detect_and_update_container()

            return {
                "id": record.id,
                "success": True,
                "detection_result": detection_result,
            }

        except Exception as e:
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
                context = {}

        return {
            "name": f"GPS Dashboard - {self.name}",
            "type": "ir.actions.client",
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
                return surface_ha

            return 0.0

        except Exception as e:
            return 0.0

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
