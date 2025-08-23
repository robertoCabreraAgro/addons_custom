# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migration script for GPS Tracking module v1.5
    Prepares the database for fleet -> product_asset migration
    """
    _logger.info("Starting GPS Tracking pre-migration checks...")
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    try:
        # 1. Check if product_asset module is installed
        _check_product_asset_module(cr, env)
        
        # 2. Log current state for rollback reference
        _log_current_state(cr, env)
        
        # 3. Check for data integrity issues
        _check_data_integrity(cr, env)
        
        # 4. Clean up foreign key references
        _cleanup_foreign_key_references(cr, env)
        
        _logger.info("GPS Tracking pre-migration checks completed successfully!")
        
    except Exception as e:
        _logger.error(f"GPS Tracking pre-migration failed: {str(e)}")
        raise


def _check_product_asset_module(cr, env):
    """Verify that product_asset module is installed"""
    _logger.info("Checking product_asset module availability...")
    
    cr.execute("""
        SELECT state 
        FROM ir_module_module 
        WHERE name = 'product_asset'
    """)
    
    result = cr.fetchone()
    if not result or result[0] != 'installed':
        raise Exception("product_asset module must be installed before migrating gps_tracking")
    
    _logger.info("product_asset module is installed and ready")


def _log_current_state(cr, env):
    """Log current state for potential rollback"""
    _logger.info("Logging current GPS tracking state...")
    
    # Count devices with fleet references
    cr.execute("""
        SELECT COUNT(*) 
        FROM gps_tracking_device 
        WHERE vehicle_id IS NOT NULL
    """)
    device_count = cr.fetchone()[0]
    
    # Count points with fleet references  
    cr.execute("""
        SELECT COUNT(*)
        FROM gps_tracking_point
        WHERE vehicle_id IS NOT NULL
    """)
    point_count = cr.fetchone()[0]
    
    _logger.info(f"Current state: {device_count} devices, {point_count} points with vehicle references")


def _check_data_integrity(cr, env):
    """Check for potential data integrity issues"""
    _logger.info("Checking data integrity...")
    
    # Check for devices pointing to non-existent vehicles
    cr.execute("""
        SELECT gtd.id, gtd.vehicle_id
        FROM gps_tracking_device gtd
        LEFT JOIN fleet_vehicle fv ON gtd.vehicle_id = fv.id
        WHERE gtd.vehicle_id IS NOT NULL AND fv.id IS NULL
    """)
    
    orphaned_devices = cr.fetchall()
    if orphaned_devices:
        _logger.warning(f"Found {len(orphaned_devices)} devices pointing to non-existent vehicles")
        for device_id, vehicle_id in orphaned_devices:
            _logger.warning(f"  - Device {device_id} -> Vehicle {vehicle_id} (missing)")
    
    # Check for vehicles without corresponding assets
    cr.execute("""
        SELECT DISTINCT gtd.vehicle_id, fv.name, fv.license_plate
        FROM gps_tracking_device gtd
        JOIN fleet_vehicle fv ON gtd.vehicle_id = fv.id
        WHERE NOT EXISTS (
            SELECT 1 FROM stock_lot sl 
            WHERE sl.license_plate = fv.license_plate 
               OR sl.vin_sn = fv.vin_sn 
               OR sl.name = fv.name
        )
    """)
    
    unmapped_vehicles = cr.fetchall()
    if unmapped_vehicles:
        _logger.warning(f"Found {len(unmapped_vehicles)} fleet vehicles without corresponding product assets")
        for vehicle_id, name, license_plate in unmapped_vehicles:
            _logger.warning(f"  - Vehicle {vehicle_id}: {name} ({license_plate}) has no matching asset")
    
    _logger.info("Data integrity check completed")


def _cleanup_foreign_key_references(cr, env):
    """Clean up invalid foreign key references before field type changes"""
    _logger.info("Cleaning up foreign key references...")
    
    # Clean up account_analytic_line.vehicle_id references
    _cleanup_analytic_line_vehicle_refs(cr)


def _cleanup_analytic_line_vehicle_refs(cr):
    """Clean up invalid vehicle_id references in account_analytic_line"""
    _logger.info("Cleaning up account_analytic_line vehicle_id references...")
    
    # First, drop any existing foreign key constraint to avoid conflicts
    try:
        cr.execute("""
            ALTER TABLE account_analytic_line 
            DROP CONSTRAINT IF EXISTS account_analytic_line_vehicle_id_fkey
        """)
        _logger.info("Dropped existing foreign key constraint for vehicle_id")
    except Exception as e:
        _logger.info(f"No existing foreign key constraint to drop: {e}")
    
    # Find ALL records with vehicle_id that don't exist in stock_lot
    cr.execute("""
        SELECT COUNT(*) 
        FROM account_analytic_line 
        WHERE vehicle_id IS NOT NULL 
        AND NOT EXISTS (
            SELECT 1 FROM stock_lot 
            WHERE id = vehicle_id
        )
    """)
    invalid_count = cr.fetchone()[0]
    
    if invalid_count > 0:
        _logger.info(f"Found {invalid_count} account_analytic_line records with invalid vehicle_id references")
        
        # Log specific invalid IDs for debugging
        cr.execute("""
            SELECT DISTINCT vehicle_id 
            FROM account_analytic_line 
            WHERE vehicle_id IS NOT NULL 
            AND NOT EXISTS (
                SELECT 1 FROM stock_lot 
                WHERE id = vehicle_id
            )
            LIMIT 10
        """)
        invalid_ids = cr.fetchall()
        _logger.info(f"Invalid vehicle_ids found: {[row[0] for row in invalid_ids]}")
        
        # Set ALL invalid references to NULL
        cr.execute("""
            UPDATE account_analytic_line 
            SET vehicle_id = NULL 
            WHERE vehicle_id IS NOT NULL 
            AND NOT EXISTS (
                SELECT 1 FROM stock_lot 
                WHERE id = vehicle_id
            )
        """)
        cleaned_count = cr.rowcount
        
        _logger.info(f"Cleaned {cleaned_count} invalid vehicle_id references (set to NULL)")
        
        # Verify cleanup
        cr.execute("""
            SELECT COUNT(*) 
            FROM account_analytic_line 
            WHERE vehicle_id IS NOT NULL 
            AND NOT EXISTS (
                SELECT 1 FROM stock_lot 
                WHERE id = vehicle_id
            )
        """)
        remaining_invalid = cr.fetchone()[0]
        _logger.info(f"Remaining invalid references after cleanup: {remaining_invalid}")
        
    else:
        _logger.info("No invalid vehicle_id references found in account_analytic_line")