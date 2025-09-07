# Base GeoEngine - Developer Usage Guide

## The Beauty: It Just Works™

With base_geoengine, spatial queries work exactly like regular Odoo searches. No special methods, no different syntax - just use `search()` as you normally would.

## Simple Examples

### Basic Spatial Search
```python
# Find all partners within a geographic area
partners = self.env['res.partner'].search([
    ('location', 'geo_within', 'POLYGON((10 10, 20 10, 20 20, 10 20, 10 10))')
])

# Find warehouses that intersect with a delivery zone
warehouses = self.env['stock.warehouse'].search([
    ('coverage_area', 'geo_intersect', delivery_zone_polygon)
])

# Find all locations within 5km of a point (if using projected coordinates)
nearby = self.env['my.location'].search([
    ('position', 'geo_within', 'CIRCLE((100.5 200.3) 5000)')
])
```

### Combining with Regular Operators
```python
# Active partners in a specific area
active_partners = self.env['res.partner'].search([
    ('active', '=', True),
    ('customer_rank', '>', 0),
    ('location', 'geo_within', city_boundary)
])

# Large warehouses in delivery zone
warehouses = self.env['stock.warehouse'].search([
    ('surface_area', '>', 1000),
    ('coverage_area', 'geo_intersect', delivery_zone),
    ('active', '=', True)
])
```

### Complex Domains with OR/AND Logic
```python
# Partners either in city center OR near highway
partners = self.env['res.partner'].search([
    '|',
        ('location', 'geo_within', city_center),
        ('location', 'geo_intersect', highway_corridor)
])

# Complex multi-condition search
locations = self.env['my.location'].search([
    ('active', '=', True),
    '|',
        '&',
            ('type', '=', 'warehouse'),
            ('area', 'geo_greater', 5000),
        '&',
            ('type', '=', 'store'),
            ('location', 'geo_within', shopping_district)
])
```

### Negation (NOT operator)
```python
# Find locations NOT in restricted area
allowed_locations = self.env['my.location'].search([
    '!', ('location', 'geo_within', restricted_zone)
])

# Active partners not in competitor territories
our_partners = self.env['res.partner'].search([
    ('active', '=', True),
    '!', ('location', 'geo_intersect', competitor_territories)
])
```

## All Search Methods Work

### search_count()
```python
# Count partners in area
partner_count = self.env['res.partner'].search_count([
    ('location', 'geo_within', city_boundary)
])
```

### search_read()
```python
# Get partner data for those in area
partner_data = self.env['res.partner'].search_read(
    [('location', 'geo_intersect', delivery_zone)],
    fields=['name', 'email', 'location']
)
```

### browse() with searched IDs
```python
# Standard pattern works perfectly
domain = [
    ('active', '=', True),
    ('location', 'geo_within', area)
]
partner_ids = self.env['res.partner'].search(domain).ids
partners = self.env['res.partner'].browse(partner_ids)
```

## Available Geo Operators

All geo operators work exactly like standard Odoo operators:

- `geo_intersect` - Geometries intersect
- `geo_within` - Geometry is within another
- `geo_contains` - Geometry contains another  
- `geo_touch` - Geometries touch (share boundary)
- `geo_equal` - Geometries are equal
- `geo_greater` - Area is greater than value/other geometry
- `geo_lesser` - Area is less than value/other geometry

## Geometry Input Formats

You can use any of these formats for geometry values:

```python
# WKT (Well-Known Text)
'POINT(10.5 20.3)'
'LINESTRING(0 0, 10 10, 20 25)'
'POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))'

# GeoJSON
{
    "type": "Point",
    "coordinates": [10.5, 20.3]
}

# Shapely objects (if you're working with them)
from shapely.geometry import Point, Polygon
point = Point(10.5, 20.3)
polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
```

## Performance Tips

1. **Use bounding boxes for initial filtering**
   ```python
   # First filter by bounding box (fast), then precise shape
   records = self.search([
       ('location', 'geo_intersect', bounding_box),
       ('location', 'geo_within', precise_shape)
   ])
   ```

2. **Combine conditions in single search**
   ```python
   # Good - single search
   results = self.search([
       ('active', '=', True),
       ('location', 'geo_within', area),
       ('type', '=', 'warehouse')
   ])
   
   # Avoid - multiple searches
   results = self.search([('active', '=', True)])
   results = results.filtered(lambda r: 
       self.search([('id', '=', r.id), ('location', 'geo_within', area)])
   )
   ```

3. **Spatial indexes are automatically used**
   - PostGIS spatial indexes are utilized automatically
   - No special configuration needed

## Integration with Existing Code

The beauty is there's no special integration needed! Your existing Odoo code continues to work, and you can start using geo operators immediately:

```python
class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    def find_nearest_warehouse(self):
        """Find warehouse that covers this delivery location."""
        # Just use search normally with geo operators!
        warehouse = self.env['stock.warehouse'].search([
            ('active', '=', True),
            ('coverage_area', 'geo_contains', self.delivery_location)
        ], limit=1)
        return warehouse
    
    def get_regional_pickings(self, region_polygon):
        """Get all pickings in a region."""
        # Works with standard search - no special methods!
        return self.search([
            ('state', 'not in', ['done', 'cancel']),
            ('delivery_location', 'geo_within', region_polygon)
        ])
```

## That's It!

No special APIs to learn. No different search methods. Just use Odoo's search() with geo operators like any other operator. It just works!