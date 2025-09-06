from odoo.tests import common

try:
    from shapely.geometry import Point, LineString, Polygon
    import geojson

    HAS_GEOSPATIAL = True
except ImportError:
    HAS_GEOSPATIAL = False


class GeoEngineTestCase(common.TransactionCase):
    """Base test case for geoengine tests with common fixtures."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not HAS_GEOSPATIAL:
            cls.skipTest(cls, "Geospatial libraries not available")

        # Common test geometries in Web Mercator (EPSG:3857)
        cls.zurich_point = Point(948695.5, 6002729.5)  # Zurich approx
        cls.geneva_point = Point(673508.2, 5863471.4)  # Geneva approx

        # Test polygon covering part of Switzerland
        cls.swiss_bbox = Polygon(
            [
                (600000, 5700000),  # SW
                (1200000, 5700000),  # SE
                (1200000, 6100000),  # NE
                (600000, 6100000),  # NW
                (600000, 5700000),  # Close polygon
            ]
        )

        # Test line (highway-like)
        cls.test_highway = LineString(
            [
                (673508, 5863471),  # Geneva area
                (750000, 5900000),  # Intermediate point
                (948695, 6002729),  # Zurich area
            ]
        )

        # Small test polygon around Zurich
        cls.zurich_area = Polygon(
            [
                (940000, 5995000),
                (955000, 5995000),
                (955000, 6010000),
                (940000, 6010000),
                (940000, 5995000),
            ]
        )

        # Test point outside Switzerland
        cls.paris_point = Point(260403.4, 6250373.2)  # Paris approx

    def assertGeometryEqual(self, geom1, geom2, tolerance=1.0):
        """Assert that two geometries are equal within tolerance."""
        if geom1 is None and geom2 is None:
            return

        self.assertIsNotNone(geom1, "First geometry is None")
        self.assertIsNotNone(geom2, "Second geometry is None")

        # Use buffer(0) to normalize geometries
        normalized_geom1 = geom1.buffer(0)
        normalized_geom2 = geom2.buffer(0)

        # Check if geometries are almost equal within tolerance
        distance = normalized_geom1.distance(normalized_geom2)
        self.assertLess(
            distance,
            tolerance,
            f"Geometries differ by {distance}, tolerance: {tolerance}",
        )

    def assertSpatialRelation(self, geom1, geom2, relation):
        """Assert a spatial relationship between two geometries."""
        relations = {
            "intersects": lambda g1, g2: g1.intersects(g2),
            "contains": lambda g1, g2: g1.contains(g2),
            "within": lambda g1, g2: g1.within(g2),
            "touches": lambda g1, g2: g1.touches(g2),
            "equals": lambda g1, g2: g1.equals(g2),
            "disjoint": lambda g1, g2: g1.disjoint(g2),
        }

        self.assertIn(relation, relations, f"Unknown spatial relation: {relation}")

        relation_func = relations[relation]
        self.assertTrue(
            relation_func(geom1, geom2),
            f"Geometries do not have expected '{relation}' relationship",
        )


class PostGISTestMixin:
    """Mixin for tests that require PostGIS functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._check_postgis_available()

    @classmethod
    def _check_postgis_available(cls):
        """Check if PostGIS is available in the test database."""
        try:
            cls.env.cr.execute("SELECT postgis_version()")
            result = cls.env.cr.fetchone()
            if not result:
                cls.skipTest(cls, "PostGIS not available in test database")
        except Exception:
            cls.skipTest(cls, "PostGIS not available in test database")

    def execute_postgis_query(self, query, params=None):
        """Execute a PostGIS query and return results."""
        self.env.cr.execute(query, params or [])
        return self.env.cr.fetchall()

    def create_test_geometry_table(self, table_name, geom_type="POINT", srid=3857):
        """Create a test table with geometry column."""
        self.env.cr.execute(
            f"""
            CREATE TEMPORARY TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                geom GEOMETRY({geom_type}, {srid})
            )
        """
        )

        # Create spatial index
        self.env.cr.execute(
            f"""
            CREATE INDEX {table_name}_geom_idx 
            ON {table_name} USING GIST (geom)
        """
        )

    def insert_test_geometry(self, table_name, name, wkt, srid=3857):
        """Insert a test geometry into table."""
        self.env.cr.execute(
            f"""
            INSERT INTO {table_name} (name, geom) 
            VALUES (%s, ST_GeomFromText(%s, %s))
        """,
            (name, wkt, srid),
        )


class MockCursorMixin:
    """Mixin providing mock database cursor functionality."""

    def create_mock_cursor(self, query_results=None):
        """Create a mock cursor with predefined results."""
        from unittest.mock import Mock

        mock_cursor = Mock()
        self.executed_queries = []
        self.executed_params = []

        def mock_execute(query, params=None):
            self.executed_queries.append(query)
            self.executed_params.append(params)

        def mock_fetchall():
            if query_results:
                return query_results.pop(0) if query_results else []
            return []

        def mock_fetchone():
            results = mock_fetchall()
            return results[0] if results else None

        mock_cursor.execute = mock_execute
        mock_cursor.fetchall = mock_fetchall
        mock_cursor.fetchone = mock_fetchone

        return mock_cursor

    def assert_sql_contains(self, expected_fragments):
        """Assert that executed SQL contains expected fragments."""
        all_sql = " ".join(self.executed_queries)
        for fragment in expected_fragments:
            self.assertIn(
                fragment,
                all_sql,
                f"SQL fragment '{fragment}' not found in executed queries",
            )

    def assert_postgis_function_called(self, function_name):
        """Assert that a specific PostGIS function was called."""
        self.assert_sql_contains([function_name])

    def get_last_query_params(self):
        """Get parameters from the last executed query."""
        return self.executed_params[-1] if self.executed_params else None
