# Base GeoEngine Test Suite

This directory contains comprehensive tests for the base_geoengine module, designed to ensure compatibility with Odoo ORM changes and validate spatial functionality.

## Test Modules

### 1. `test_geo_fields.py`
Tests geo field functionality and ORM integration:
- Field type registration in Odoo namespace
- PostGIS column type generation
- Geometry conversion (WKT, GeoJSON, Shapely)
- Validation and error handling
- SRID and dimension handling
- Helper methods (lat/lon conversion)

### 2. `test_geo_operators.py` 
Tests spatial operators and SQL generation:
- All 7 spatial operators (contains, intersects, within, etc.)
- SQL parameter binding and injection prevention
- Complex geometry handling
- Different SRID handling
- Error cases and edge conditions

### 3. `test_orm_compatibility.py`
Tests ORM interface stability and compatibility:
- BaseModel inheritance structure
- Search method signature stability
- Fields_get method compatibility
- Field registration mechanisms
- Domain processing compatibility
- API decorator availability
- Exception class availability

### 4. `test_spatial_queries.py`
Tests spatial query integration and execution:
- Search method override functionality
- Domain processing with geo operators
- Multiple geo operators in single domain
- Mixed geo and regular operator domains
- Error handling and graceful fallbacks
- Limit, offset, and ordering with geo queries

## Running Tests

### Prerequisites
1. **PostGIS Database**: Tests require a PostgreSQL database with PostGIS extensions
2. **Python Dependencies**: shapely, geojson, simplejson
3. **Odoo Installation**: Working Odoo 18.2+ installation

### Install Dependencies
```bash
pip install shapely geojson simplejson
```

### Running All Tests
```bash
# Basic run
python tests/test_runner.py

# Verbose output
python tests/test_runner.py --verbose

# Custom database
python tests/test_runner.py --database my_test_db

# Custom odoo-bin path
python tests/test_runner.py --odoo-bin /path/to/odoo-bin
```

### Running Specific Test Module
```bash
# Run only geo fields tests
python tests/test_runner.py --test-module test_geo_fields

# Run only ORM compatibility tests
python tests/test_runner.py --test-module test_orm_compatibility
```

### Running with Odoo Test Command
```bash
# Run all base_geoengine tests
odoo-bin --test-enable --test-tags base_geoengine --database test_db --addons-path /path/to/addons --init base_geoengine --stop-after-init

# Run specific test class
odoo-bin --test-enable --test-tags base_geoengine.test_geo_fields --database test_db --addons-path /path/to/addons --init base_geoengine --stop-after-init
```

## Test Structure

### Base Test Classes
- `GeoEngineTestCase`: Base class with common test geometries and utilities
- `PostGISTestMixin`: Mixin for tests requiring PostGIS database functionality  
- `MockCursorMixin`: Mixin for mocking database cursor operations

### Test Geometries
Tests use realistic Swiss coordinate data in Web Mercator projection (EPSG:3857):
- Zurich point: `Point(948695.5, 6002729.5)`
- Geneva point: `Point(673508.2, 5863471.4)`
- Swiss bounding box polygon
- Highway line connecting Geneva to Zurich
- Test areas and validation geometries

### Assertion Helpers
- `assertGeometryEqual()`: Compare geometries within tolerance
- `assertSpatialRelation()`: Assert spatial relationships (contains, intersects, etc.)
- `assert_sql_contains()`: Verify SQL query content
- `assert_postgis_function_called()`: Verify PostGIS function usage

## Test Categories

### Unit Tests
- Field type definitions
- SQL generation logic  
- Geometry conversion functions
- Validation methods

### Integration Tests
- Search method overrides
- Domain processing
- Database query execution
- Error handling flows

### Compatibility Tests
- ORM interface stability
- API signature verification
- Inheritance chain validation
- Exception handling

## Continuous Integration

### Automated Testing
The test suite is designed for CI/CD integration:

```yaml
# Example GitHub Actions workflow
name: GeoEngine Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:13-3.1
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install shapely geojson simplejson
      - name: Run tests
        run: |
          python addons_custom/base_geoengine/tests/test_runner.py --verbose
```

### Pre-commit Hooks
Add to `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: local
    hooks:
      - id: geoengine-tests
        name: Run GeoEngine Tests
        entry: python addons_custom/base_geoengine/tests/test_runner.py
        language: system
        pass_filenames: false
        files: addons_custom/base_geoengine/
```

## Debugging Failed Tests

### Common Issues

#### PostGIS Not Available
```
Error: PostGIS not available in test database
```
**Solution**: Install PostGIS extensions in test database:
```sql
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
```

#### Missing Python Dependencies
```
ImportError: No module named 'shapely'
```
**Solution**: Install geospatial dependencies:
```bash
pip install shapely geojson simplejson
```

#### ORM Compatibility Issues
```
AttributeError: 'Query' object has no attribute 'where'
```
**Cause**: Odoo ORM API changed
**Solution**: Update base_geoengine code to use new ORM interface

### Test Output Analysis
The test runner provides detailed analysis:
- **ORM Compatibility Check**: Detects potential API changes
- **PostGIS Compatibility Check**: Identifies spatial database issues
- **SQL Query Verification**: Validates generated PostGIS queries
- **Error Pattern Recognition**: Categorizes common failure modes

### Debug Mode
Run tests with maximum verbosity:
```bash
python tests/test_runner.py --verbose
```

This provides:
- Full SQL queries executed
- Parameter values passed
- Complete error tracebacks
- ORM method call traces

## Test Data Management

### Test Database Setup
Tests use temporary tables and transactions:
- Each test runs in isolated transaction
- PostGIS functions tested with real spatial data
- Test geometries cleaned up automatically

### Geometry Fixtures
Consistent test data across all test modules:
- Swiss coordinate system (appropriate for EU deployment)
- Realistic geographic relationships
- Edge cases (empty geometries, invalid data)
- Multiple geometry types and complexity levels

## Maintenance

### Adding New Tests
1. Create test method in appropriate test module
2. Use existing base classes and mixins
3. Follow naming convention: `test_feature_description`
4. Add docstring explaining test purpose
5. Use assertion helpers for consistent validation

### Updating for New Odoo Versions
1. Run ORM compatibility tests first
2. Check for deprecation warnings
3. Update method signatures if needed
4. Verify field registration still works
5. Test spatial query execution

### Monitoring ORM Changes
The compatibility tests will detect:
- Method signature changes
- Missing attributes or methods
- Changed inheritance hierarchies
- New required parameters
- Deprecated functionality

These tests ensure that base_geoengine remains compatible as Odoo evolves, providing early warning of breaking changes and guidance for necessary updates.