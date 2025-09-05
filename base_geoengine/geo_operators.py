class GeoOperator:
    """PostGIS spatial operator SQL generator for geographic field operations.

    This class provides methods to generate raw SQL queries for spatial operations
    using PostGIS functions. It handles various geometric comparisons and spatial
    relationships commonly used in GIS applications.

    Attributes:
        geo_field (GeoField): The geographic field instance to operate on.
    """

    def __init__(self, geo_field):
        """Initialize GeoOperator with a geographic field.

        Args:
            geo_field (GeoField): Geographic field instance that provides geometry
                                 type information and conversion methods.
        """
        self.geo_field = geo_field

    def _get_direct_como_op_sql(self, table, col, value, params, op=""):
        """Generate SQL for direct area comparison operations.

        Creates raw SQL for comparing geometric area values using PostGIS ST_Area function.
        Supports both numeric values and geometric objects as comparison targets.

        Args:
            table (str): Database table name containing the geometry column.
            col (str): Name of the geometry column to compare.
            value (int|float|geometry): Comparison value - either numeric area or geometry.
            params (list): SQL parameter list to append values to.
            op (str): SQL comparison operator (>, <, =, etc.).

        Returns:
            str: Raw SQL fragment for area comparison operation.
        """
        if isinstance(value, int | float):
            return f" ST_Area({table}.{col}) {op} {value}"
        else:
            base = self.geo_field.entry_to_shape(value, same_type=False)
            params.append(base.wkt)
            return f" ST_Area({table}.{col}) {op} ST_Area(ST_GeomFromText(%s))"

    def _get_postgis_comp_sql(self, table, col, value, params, op=""):
        """Generate SQL for PostGIS spatial comparison operations.

        Creates raw SQL for spatial relationship tests using PostGIS ST_* functions.
        Handles geometry conversion and SRID coordination for proper spatial operations.

        Args:
            table (str): Database table name containing the geometry column.
            col (str): Name of the geometry column to compare.
            value (geometry): Geometry object to compare against.
            params (list): SQL parameter list to append WKT and SRID values.
            op (str): PostGIS function name (ST_Intersects, ST_Contains, etc.).

        Returns:
            str: Raw SQL fragment for spatial comparison operation.
        """
        base = self.geo_field.entry_to_shape(value, same_type=False)
        srid = self.geo_field.srid
        params.append(base.wkt)
        params.append(srid)
        return f"{op}({table}.{col}, ST_GeomFromText(%s, %s))"

    def get_geo_greater_sql(self, table, col, value, params):
        """Generate SQL for greater-than area comparison.

        Creates SQL to find geometries with area greater than the specified value.

        Args:
            table (str): Database table name.
            col (str): Geometry column name.
            value (int|float|geometry): Comparison threshold.
            params (list): SQL parameter list.

        Returns:
            str: SQL fragment for area > value comparison.
        """
        return self._get_direct_como_op_sql(table, col, value, params, op=">")

    def get_geo_lesser_sql(self, table, col, value, params):
        """Generate SQL for less-than area comparison.

        Creates SQL to find geometries with area less than the specified value.

        Args:
            table (str): Database table name.
            col (str): Geometry column name.
            value (int|float|geometry): Comparison threshold.
            params (list): SQL parameter list.

        Returns:
            str: SQL fragment for area < value comparison.
        """
        return self._get_direct_como_op_sql(table, col, value, params, op="<")

    def get_geo_equal_sql(self, table, col, value, params):
        """Generate SQL for geometric equality comparison.

        Creates SQL to find geometries that are exactly equal to the specified geometry.
        Uses direct geometry comparison without spatial functions.

        Args:
            table (str): Database table name.
            col (str): Geometry column name.
            value (geometry): Geometry to compare against.
            params (list): SQL parameter list.

        Returns:
            str: SQL fragment for geometry equality comparison.
        """
        base = self.geo_field.entry_to_shape(value, same_type=False)
        compare_to = "ST_GeomFromText(%s)"
        params.append(base.wkt)
        return f" {table}.{col} = {compare_to}"

    def get_geo_intersect_sql(self, table, col, value, params):
        """Generate SQL for spatial intersection test.

        Creates SQL using ST_Intersects to find geometries that spatially
        intersect with the specified geometry.

        Args:
            table (str): Database table name.
            col (str): Geometry column name.
            value (geometry): Geometry to test intersection against.
            params (list): SQL parameter list.

        Returns:
            str: SQL fragment for ST_Intersects spatial comparison.
        """
        return self._get_postgis_comp_sql(table, col, value, params, op="ST_Intersects")

    def get_geo_touch_sql(self, table, col, value, params):
        """Generate SQL for spatial touch test.

        Creates SQL using ST_Touches to find geometries that touch the
        specified geometry (share boundary but no interior points).

        Args:
            table (str): Database table name.
            col (str): Geometry column name.
            value (geometry): Geometry to test touching against.
            params (list): SQL parameter list.

        Returns:
            str: SQL fragment for ST_Touches spatial comparison.
        """
        return self._get_postgis_comp_sql(table, col, value, params, op="ST_Touches")

    def get_geo_within_sql(self, table, col, value, params):
        """Generate SQL for spatial containment test (within).

        Creates SQL using ST_Within to find geometries that are completely
        contained within the specified geometry.

        Args:
            table (str): Database table name.
            col (str): Geometry column name.
            value (geometry): Container geometry to test against.
            params (list): SQL parameter list.

        Returns:
            str: SQL fragment for ST_Within spatial comparison.
        """
        return self._get_postgis_comp_sql(table, col, value, params, op="ST_Within")

    def get_geo_contains_sql(self, table, col, value, params):
        """Generate SQL for spatial containment test (contains).

        Creates SQL using ST_Contains to find geometries that completely
        contain the specified geometry.

        Args:
            table (str): Database table name.
            col (str): Geometry column name.
            value (geometry): Contained geometry to test against.
            params (list): SQL parameter list.

        Returns:
            str: SQL fragment for ST_Contains spatial comparison.
        """
        return self._get_postgis_comp_sql(table, col, value, params, op="ST_Contains")
