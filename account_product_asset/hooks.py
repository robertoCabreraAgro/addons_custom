# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Post-installation hook for account_product_asset module
    Migrates data from account_fleet module AFTER schema is ready
    """
    _logger.info("=== Starting Account Product Asset post-installation hook ===")
    
    cr = env.cr
    
    try:
        # Check if account_fleet module exists and has data
        if not _check_account_fleet_module_availability(env):
            _logger.info("Account Fleet module not found or no data to migrate. Skipping migration.")
            return
        
        # Main migration: account_fleet -> account_product_asset
        _migrate_account_fleet_to_product_asset(env)
        
        # Validate migration results
        _validate_migration_results(env)
        
        _logger.info("=== Account Product Asset post-installation hook completed successfully ===")
        
    except Exception as e:
        _logger.error(f"Account Product Asset post-installation hook failed: {str(e)}")
        cr.rollback()
        raise UserError(f"Post-migration failed: {str(e)}")


def _check_account_fleet_module_availability(env):
    """Check if account_fleet module is installed and has data"""
    _logger.info("Checking account_fleet module availability...")
    
    cr = env.cr
    
    # Check if account_fleet module is installed
    cr.execute("""
        SELECT state 
        FROM ir_module_module 
        WHERE name = 'account_fleet'
    """)
    
    result = cr.fetchone()
    if not result or result[0] != 'installed':
        _logger.info("Account Fleet module is not installed")
        return False
    
    # Check if there are account move lines with fleet vehicles
    cr.execute("""
        SELECT COUNT(*) 
        FROM account_move_line aml
        WHERE aml.vehicle_id IS NOT NULL
    """)
    move_line_count = cr.fetchone()[0]
    
    _logger.info(f"Found {move_line_count} account move lines with fleet vehicles")
    return move_line_count > 0


def _migrate_account_fleet_to_product_asset(env):
    """Main migration from account_fleet to account_product_asset"""
    _logger.info("Starting account_fleet to account_product_asset migration...")
    
    cr = env.cr
    
    # Migrate account.move.line vehicle references
    migrated_move_lines = _migrate_move_line_vehicle_references(env)
    
    # Migrate account.move vehicle references (if any)
    migrated_moves = _migrate_move_vehicle_references(env)
    
    _logger.info(f"Migration completed: {migrated_move_lines} move lines, {migrated_moves} moves")


def _migrate_move_line_vehicle_references(env):
    """Migrate account.move.line vehicle_id references from fleet.vehicle to stock.lot"""
    _logger.info("Migrating account move line vehicle references...")
    
    cr = env.cr
    
    # First, check basic counts to understand the data
    cr.execute("SELECT COUNT(*) FROM fleet_vehicle")
    fleet_count = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM stock_lot WHERE asset_type = 'vehicle'")
    stock_count = cr.fetchone()[0]
    _logger.info(f"Database contains: {fleet_count} fleet_vehicles, {stock_count} stock_lot vehicles")
    
    # Debug: Check some sample data
    cr.execute("SELECT id, name, license_plate FROM fleet_vehicle LIMIT 3")
    fleet_sample = cr.fetchall()
    _logger.info(f"Fleet sample: {fleet_sample}")
    
    cr.execute("SELECT id, name, license_plate FROM stock_lot WHERE asset_type = 'vehicle' LIMIT 3")
    stock_sample = cr.fetchall()  
    _logger.info(f"Stock sample: {stock_sample}")
    
    # Test a few direct matches to see if mapping logic works
    _logger.info("Testing direct fleet → stock.lot matching...")
    try:
        cr.execute("""
            SELECT COUNT(*)
            FROM stock_lot sl, fleet_vehicle fv
            WHERE sl.asset_type = 'vehicle' 
            AND (
                (fv.license_plate IS NOT NULL AND fv.license_plate != '' AND 
                 sl.license_plate IS NOT NULL AND sl.license_plate != '' AND
                 fv.license_plate = sl.license_plate)
                OR 
                (fv.vin_sn IS NOT NULL AND fv.vin_sn != '' AND
                 sl.vin_sn IS NOT NULL AND sl.vin_sn != '' AND
                 fv.vin_sn = sl.vin_sn)
            )
        """)
        potential_matches = cr.fetchone()[0]
        _logger.info(f"Found {potential_matches} potential fleet → stock.lot matches")
        
        if potential_matches == 0:
            if fleet_count > 0 and stock_count == 0:
                raise UserError("No stock.lot vehicles found but fleet_vehicle records exist. "
                              "Please ensure product_asset module is installed and migration completed first.")
            elif fleet_count > 0 and stock_count > 0:
                _logger.warning(f"Data mismatch: {fleet_count} fleet vehicles but {stock_count} stock vehicles - "
                              f"license plates and VINs don't match exactly")
        
    except Exception as e:
        _logger.error(f"Error testing matches: {str(e)}")
    
    # Get all move lines with vehicle_id pointing to fleet.vehicle
    try:
        cr.execute("""
            SELECT id, vehicle_id 
            FROM account_move_line 
            WHERE vehicle_id IS NOT NULL
        """)
        move_lines_data = cr.fetchall()
    except Exception as e:
        _logger.error(f"Error getting move lines data: {str(e)}")
        return 0
    
    if not move_lines_data:
        _logger.info("No move lines with vehicle references found")
        return 0
        
    _logger.info(f"Found {len(move_lines_data)} move lines to migrate")
    
    migrated_count = 0
    failed_count = 0
    nullified_count = 0
    
    for move_line_id, old_vehicle_id in move_lines_data:
        try:
            # Find corresponding stock.lot directly without temp table
            cr.execute("""
                SELECT sl.id 
                FROM stock_lot sl, fleet_vehicle fv
                WHERE sl.asset_type = 'vehicle' 
                AND fv.id = %s
                AND (
                    (fv.license_plate IS NOT NULL AND fv.license_plate != '' AND 
                     sl.license_plate IS NOT NULL AND sl.license_plate != '' AND
                     fv.license_plate = sl.license_plate)
                    OR 
                    (fv.vin_sn IS NOT NULL AND fv.vin_sn != '' AND
                     sl.vin_sn IS NOT NULL AND sl.vin_sn != '' AND
                     fv.vin_sn = sl.vin_sn)
                )
                LIMIT 1
            """, (old_vehicle_id,))
            
            result = cr.fetchone()
            if result:
                new_asset_id = result[0]
                # Create temporary column if it doesn't exist and store the mapping
                cr.execute("""
                    ALTER TABLE account_move_line 
                    ADD COLUMN IF NOT EXISTS temp_asset_id INTEGER
                """)
                
                # Update the asset_id field with the new asset reference
                cr.execute("""
                    UPDATE account_move_line 
                    SET asset_id = %s 
                    WHERE id = %s
                """, (new_asset_id, move_line_id))
                migrated_count += 1
                _logger.debug(f"Move line {move_line_id}: fleet.vehicle({old_vehicle_id}) -> stock.lot({new_asset_id})")
            else:
                # No matching stock.lot found, leave asset_id as NULL
                _logger.debug(f"No matching stock.lot found for move line {move_line_id} with vehicle {old_vehicle_id}")
                nullified_count += 1
                
        except Exception as e:
            _logger.error(f"Error migrating move line {move_line_id}: {str(e)}")
            # Rollback and continue
            cr.rollback()
            cr = env.cr  # Get a fresh cursor
            # Skip failed records - asset_id will remain NULL
            try:
                pass  # No action needed, asset_id will remain NULL
                failed_count += 1
            except:
                pass  # If we can't even set to NULL, skip
    
    _logger.info(f"Move lines migration: {migrated_count} migrated, {nullified_count} nullified, {failed_count} failed")
    
    # Note: We don't recreate the vehicle_id constraint since we're using asset_id field instead
    _logger.info("Migration completed - data moved from old_vehicle_id to asset_id field")
    
    # Fail if too many records were nullified or failed
    total_processed = migrated_count + nullified_count + failed_count
    success_rate = migrated_count / total_processed if total_processed > 0 else 0
    
    _logger.info(f"Migration success rate: {success_rate:.2%} ({migrated_count}/{total_processed})")
    
    if total_processed > 0 and success_rate < 0.5:  # Less than 50% successfully migrated
        raise UserError(f"Migration failed: Only {success_rate:.1%} of records successfully migrated. "
                       f"Expected better mapping between fleet_vehicle and stock_lot. "
                       f"Check data consistency before proceeding.")
    
    if nullified_count > migrated_count and total_processed > 100:  # More nullified than migrated (only for large datasets)
        _logger.warning(f"Warning: {nullified_count} records were set to NULL vs {migrated_count} migrated")
    
    return migrated_count


def _migrate_move_vehicle_references(env):
    """Migrate account.move vehicle_id references from fleet.vehicle to stock.lot (if any)"""
    _logger.info("Migrating account move vehicle references...")
    
    cr = env.cr
    
    # Check if account_move has vehicle_id column
    try:
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'account_move' AND column_name = 'vehicle_id'
        """)
        
        if not cr.fetchone():
            _logger.info("No vehicle_id column in account_move table, skipping")
            return 0
    except Exception as e:
        _logger.error(f"Error checking account_move columns: {str(e)}")
        return 0
    
    # Get all moves with vehicle_id pointing to fleet.vehicle
    try:
        cr.execute("""
            SELECT id, vehicle_id 
            FROM account_move 
            WHERE vehicle_id IS NOT NULL
        """)
        moves_data = cr.fetchall()
    except Exception as e:
        _logger.error(f"Error getting moves data: {str(e)}")
        return 0
    
    if not moves_data:
        _logger.info("No moves with vehicle references found")
        return 0
        
    _logger.info(f"Found {len(moves_data)} moves to migrate")
    
    migrated_count = 0
    failed_count = 0
    nullified_count = 0
    
    for move_id, old_vehicle_id in moves_data:
        try:
            # Find corresponding stock.lot by matching key fields
            cr.execute("""
                SELECT sl.id 
                FROM stock_lot sl
                JOIN fleet_vehicle fv ON (
                    sl.license_plate = fv.license_plate 
                    OR (sl.vin_sn = fv.vin_sn AND sl.vin_sn IS NOT NULL)
                    OR (sl.name = fv.name)
                )
                WHERE fv.id = %s 
                AND sl.asset_type = 'vehicle'
                LIMIT 1
            """, (old_vehicle_id,))
            
            result = cr.fetchone()
            if result:
                new_asset_id = result[0]
                # Update the reference
                cr.execute("""
                    UPDATE account_move 
                    SET vehicle_id = %s 
                    WHERE id = %s
                """, (new_asset_id, move_id))
                migrated_count += 1
                _logger.debug(f"Move {move_id}: fleet.vehicle({old_vehicle_id}) -> stock.lot({new_asset_id})")
            else:
                # Vehicle not migrated, set to NULL to avoid issues
                _logger.warning(f"No matching stock.lot found for move {move_id} with vehicle {old_vehicle_id}, setting to NULL")
                cr.execute("""
                    UPDATE account_move 
                    SET vehicle_id = NULL 
                    WHERE id = %s
                """, (move_id,))
                nullified_count += 1
                
        except Exception as e:
            _logger.error(f"Error migrating move {move_id}: {str(e)}")
            # Continue with other moves
            failed_count += 1
    
    _logger.info(f"Moves migration: {migrated_count} migrated, {nullified_count} nullified, {failed_count} failed")
    return migrated_count


def _validate_migration_results(env):
    """Validate that migration was successful"""
    _logger.info("Validating migration results...")
    
    cr = env.cr
    
    # Count move lines with valid asset references (migrated data)
    cr.execute("""
        SELECT COUNT(*) 
        FROM account_move_line aml
        JOIN stock_lot sl ON aml.asset_id = sl.id
        WHERE aml.asset_id IS NOT NULL
        AND sl.asset_type = 'vehicle'
    """)
    valid_move_lines = cr.fetchone()[0]
    
    # Count move lines with vehicle_id that weren't migrated to asset_id (orphaned)
    cr.execute("""
        SELECT COUNT(*) 
        FROM account_move_line aml
        WHERE aml.vehicle_id IS NOT NULL AND aml.asset_id IS NULL
    """)
    orphaned_move_lines = cr.fetchone()[0]
    
    # Check if account_move has vehicle_id column and count references
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'account_move' AND column_name = 'vehicle_id'
    """)
    
    valid_moves = 0
    orphaned_moves = 0
    
    if cr.fetchone():
        # Count moves with valid vehicle references
        cr.execute("""
            SELECT COUNT(*) 
            FROM account_move am
            JOIN stock_lot sl ON am.vehicle_id = sl.id
            WHERE am.vehicle_id IS NOT NULL
            AND sl.asset_type = 'vehicle'
        """)
        valid_moves = cr.fetchone()[0]
        
        # Count moves with invalid vehicle references
        cr.execute("""
            SELECT COUNT(*) 
            FROM account_move am
            LEFT JOIN stock_lot sl ON am.vehicle_id = sl.id
            WHERE am.vehicle_id IS NOT NULL AND sl.id IS NULL
        """)
        orphaned_moves = cr.fetchone()[0]
    
    _logger.info("=== Migration Results ===")
    _logger.info(f"Valid move lines with asset references: {valid_move_lines}")
    _logger.info(f"Orphaned move lines: {orphaned_move_lines}")
    _logger.info(f"Valid moves with asset references: {valid_moves}")
    _logger.info(f"Orphaned moves: {orphaned_moves}")
    
    if orphaned_move_lines > 0 or orphaned_moves > 0:
        _logger.warning(f"Migration incomplete: {orphaned_move_lines + orphaned_moves} records with invalid references")
    else:
        _logger.info("All accounting references migrated successfully!")
    
    return {
        'valid_move_lines': valid_move_lines,
        'orphaned_move_lines': orphaned_move_lines,
        'valid_moves': valid_moves,
        'orphaned_moves': orphaned_moves,
    }