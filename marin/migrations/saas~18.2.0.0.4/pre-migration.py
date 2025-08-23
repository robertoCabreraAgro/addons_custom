# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migration script for Marin module v1.2
    Cleans up invalid vehicle_id references before fleet -> product_asset migration
    """
    _logger.info("Starting Marin pre-migration cleanup...")
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    try:
        # Clean up approval_request.vehicle_id references
        _cleanup_approval_request_vehicle_refs(cr)
        
        # Clean up other vehicle_id references if they exist
        _cleanup_other_vehicle_references(cr)
        
        _logger.info("Marin pre-migration cleanup completed successfully!")
        
    except Exception as e:
        _logger.error(f"Marin pre-migration failed: {str(e)}")
        raise


def _cleanup_approval_request_vehicle_refs(cr):
    """Clean up invalid vehicle_id references in approval_request"""
    _logger.info("Cleaning up approval_request vehicle_id references...")
    
    # Check if approval_request table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'approval_request'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info("approval_request table does not exist, skipping cleanup")
        return
    
    # Check if vehicle_id column exists
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = 'approval_request' 
            AND column_name = 'vehicle_id'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info("approval_request.vehicle_id column does not exist, skipping cleanup")
        return
    
    # Find ALL records with vehicle_id that don't exist in stock_lot
    cr.execute("""
        SELECT COUNT(*) 
        FROM approval_request 
        WHERE vehicle_id IS NOT NULL 
        AND NOT EXISTS (
            SELECT 1 FROM stock_lot 
            WHERE id = vehicle_id
        )
    """)
    invalid_count = cr.fetchone()[0]
    
    if invalid_count > 0:
        _logger.info(f"Found {invalid_count} approval_request records with invalid vehicle_id references")
        
        # Log specific invalid IDs for debugging
        cr.execute("""
            SELECT DISTINCT vehicle_id 
            FROM approval_request 
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
            UPDATE approval_request 
            SET vehicle_id = NULL 
            WHERE vehicle_id IS NOT NULL 
            AND NOT EXISTS (
                SELECT 1 FROM stock_lot 
                WHERE id = vehicle_id
            )
        """)
        cleaned_count = cr.rowcount
        
        _logger.info(f"Cleaned {cleaned_count} invalid vehicle_id references in approval_request")
        
        # Verify cleanup
        cr.execute("""
            SELECT COUNT(*) 
            FROM approval_request 
            WHERE vehicle_id IS NOT NULL 
            AND NOT EXISTS (
                SELECT 1 FROM stock_lot 
                WHERE id = vehicle_id
            )
        """)
        remaining_invalid = cr.fetchone()[0]
        _logger.info(f"Remaining invalid references after cleanup: {remaining_invalid}")
        
    else:
        _logger.info("No invalid vehicle_id references found in approval_request")


def _cleanup_other_vehicle_references(cr):
    """Clean up other invalid vehicle_id references in marin module tables"""
    _logger.info("Checking for other vehicle_id references in marin module...")
    
    # List of tables that might have vehicle_id references
    tables_to_check = [
        'approval_category',
        'documents_document',
        'hr_employee',
        'mail_activity',
        'product_asset_log_import',  # The renamed wizard table
        'stock_picking',  # Add stock_picking to cleanup
        'stock_picking_tracker',  # Also check tracker table
        'account_analytic_line',  # This was mentioned in previous errors
    ]
    
    for table_name in tables_to_check:
        try:
            # Check if table and column exist
            cr.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = %s 
                    AND column_name = 'vehicle_id'
                )
            """, (table_name,))
            
            if cr.fetchone()[0]:
                # Clean up invalid references
                cr.execute(f"""
                    SELECT COUNT(*) 
                    FROM {table_name}
                    WHERE vehicle_id IS NOT NULL 
                    AND NOT EXISTS (
                        SELECT 1 FROM stock_lot 
                        WHERE id = vehicle_id
                    )
                """)
                invalid_count = cr.fetchone()[0]
                
                if invalid_count > 0:
                    _logger.info(f"Found {invalid_count} invalid vehicle_id references in {table_name}")
                    cr.execute(f"""
                        UPDATE {table_name}
                        SET vehicle_id = NULL 
                        WHERE vehicle_id IS NOT NULL 
                        AND NOT EXISTS (
                            SELECT 1 FROM stock_lot 
                            WHERE id = vehicle_id
                        )
                    """)
                    cleaned_count = cr.rowcount
                    _logger.info(f"Cleaned {cleaned_count} invalid vehicle_id references in {table_name}")
                
        except Exception as e:
            _logger.warning(f"Could not check/clean {table_name}: {str(e)}")
            continue
    
    _logger.info("Finished checking other vehicle_id references")