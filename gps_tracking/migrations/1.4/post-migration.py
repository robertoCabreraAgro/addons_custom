"""
Post-migration script for GPS Tracking module version 1.4

This migration script:
1. Creates default geofence type records if they don't exist
2. Assigns colors and sequences to existing geofences based on their area_type
3. Migrates area_size field data to surface field if needed
4. Calculates surface for existing geofences using PostGIS
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Execute post-migration tasks for version 1.4."""
    if not version:
        return
    
    _logger.info("Starting GPS Tracking module post-migration for version 1.4")
    
    # 1. Ensure geofence type records exist
    _create_default_geofence_types(cr)
    
    # 2. Update existing geofences with colors and sequences from types
    _update_geofence_colors_and_sequences(cr)
    
    # 3. Migrate area_size to surface if column exists
    _migrate_area_size_to_surface(cr)
    
    # 4. Convert existing hectare values to square meters
    _convert_hectares_to_meters(cr)
    
    # 5. Calculate surface for existing geofences
    _calculate_existing_surfaces(cr)
    
    _logger.info("GPS Tracking module post-migration for version 1.4 completed")


def _create_default_geofence_types(cr):
    """Create default geofence type records if they don't exist."""
    _logger.info("Creating default geofence type records")
    
    # Check if geofence types table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'gps_geofence_type'
        )
    """)
    
    if not cr.fetchone()[0]:
        _logger.info("gps_geofence_type table doesn't exist yet, skipping type creation")
        return
    
    # Default types configuration
    default_types = [
        ('property', 'Property', '#00008B', 10),
        ('cultivation_zone', 'Cultivation Zone', '#008000', 11),
        ('parcel', 'Parcel', '#90EE90', 11),
        ('warehouse', 'Warehouse', '#FF0000', 12),
        ('corral', 'Corral', '#FF0000', 12),
        ('other', 'Other', '#808080', 13),
    ]
    
    for code, name, color, sequence in default_types:
        # Check if type already exists
        cr.execute("""
            SELECT id FROM gps_geofence_type WHERE code = %s
        """, (code,))
        
        if not cr.fetchone():
            cr.execute("""
                INSERT INTO gps_geofence_type (name, code, color, sequence, active, create_date, write_date, create_uid, write_uid)
                VALUES (%s, %s, %s, %s, true, now(), now(), 1, 1)
            """, (name, code, color, sequence))
            _logger.info(f"Created geofence type: {name} ({code})")


def _update_geofence_colors_and_sequences(cr):
    """Update existing geofences with colors and sequences from type configuration."""
    _logger.info("Updating existing geofences with colors and sequences")
    
    # Check if both tables exist
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name IN ('gps_geofence', 'gps_geofence_type')
        ) as table_count
    """)
    
    if not cr.fetchone()[0]:
        _logger.info("Required tables don't exist yet, skipping color/sequence update")
        return
    
    # Update geofences with colors and sequences from types
    cr.execute("""
        UPDATE gps_geofence 
        SET 
            color = COALESCE(gt.color, gps_geofence.color),
            sequence = COALESCE(gt.sequence, gps_geofence.sequence),
            write_date = now()
        FROM gps_geofence_type gt
        WHERE gps_geofence.area_type = gt.code
        AND gps_geofence.area_type IS NOT NULL
    """)
    
    updated_count = cr.rowcount
    _logger.info(f"Updated {updated_count} geofences with colors and sequences")


def _migrate_area_size_to_surface(cr):
    """Migrate area_size field data to surface field if area_size column exists."""
    _logger.info("Checking for area_size field migration")
    
    # Check if area_size column exists in gps_geofence table
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'gps_geofence' 
            AND column_name = 'area_size'
        )
    """)
    
    if cr.fetchone()[0]:
        _logger.info("Migrating area_size data to surface field")
        
        # Copy data from area_size to surface where surface is null or 0
        cr.execute("""
            UPDATE gps_geofence 
            SET surface = area_size, write_date = now()
            WHERE area_size IS NOT NULL 
            AND area_size > 0 
            AND (surface IS NULL OR surface = 0)
        """)
        
        migrated_count = cr.rowcount
        _logger.info(f"Migrated {migrated_count} area_size values to surface field")
    else:
        _logger.info("area_size column not found, no migration needed")


def _convert_hectares_to_meters(cr):
    """Convert existing surface values from hectares to square meters."""
    _logger.info("Converting existing surface values from hectares to square meters")
    
    # Check if gps_geofence table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'gps_geofence'
        )
    """)
    
    if not cr.fetchone()[0]:
        _logger.info("gps_geofence table doesn't exist, skipping hectare conversion")
        return
    
    # Convert hectares to square meters (multiply by 10,000)
    cr.execute("""
        UPDATE gps_geofence 
        SET surface = surface * 10000.0, write_date = now()
        WHERE surface IS NOT NULL 
        AND surface > 0 
        AND surface < 1000000  # Assume values less than 1M are in hectares
    """)
    
    converted_count = cr.rowcount
    _logger.info(f"Converted {converted_count} surface values from hectares to square meters")


def _calculate_existing_surfaces(cr):
    """Calculate surface for existing geofences using PostGIS if geometry exists."""
    _logger.info("Calculating surface for existing geofences")
    
    # Check if gps_geofence table and PostGIS functions exist
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'gps_geofence'
        )
    """)
    
    if not cr.fetchone()[0]:
        _logger.info("gps_geofence table doesn't exist, skipping surface calculation")
        return
    
    # Check if PostGIS extension is available
    try:
        cr.execute("SELECT PostGIS_Version()")
        _logger.info("PostGIS is available, proceeding with surface calculation")
    except Exception as e:
        _logger.warning(f"PostGIS not available, skipping surface calculation: {e}")
        return
    
    # Calculate surface for geofences that have geometry but no surface
    # Surface is now in square meters (not hectares)
    cr.execute("""
        UPDATE gps_geofence 
        SET 
            surface = ST_Area(ST_Transform(geometry, 3857)),
            write_date = now()
        WHERE geometry IS NOT NULL 
        AND (surface IS NULL OR surface = 0)
    """)
    
    calculated_count = cr.rowcount
    _logger.info(f"Calculated surface for {calculated_count} geofences")