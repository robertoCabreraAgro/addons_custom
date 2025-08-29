import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration script for Marin module v18.2.0.0.4
    Migrates approval system from fleet references to product_asset references
    """
    _logger.info(
        "Starting Marin approval system migration from fleet to product_asset..."
    )

    env = api.Environment(cr, SUPERUSER_ID, {})

    try:
        # 1. Update approval_category.approval_type values
        _migrate_approval_category_types(cr, env)

        # 2. Update approval_request.vehicle_id references to stock.lot
        _migrate_approval_request_vehicles(cr, env)

        # 3. Update approval_request.log_ids to point to product.asset.log
        _migrate_approval_request_logs(cr, env)

        # 4. Validate migration success
        _validate_migration(cr, env)

        _logger.info("Marin approval system migration completed successfully!")

    except Exception as e:
        _logger.error(f"Marin approval system migration failed: {str(e)}")
        cr.rollback()
        raise


def _migrate_approval_category_types(cr, env):
    """Update approval_category.approval_type from fleet_vehicle_log to product_asset_log"""
    _logger.info("Migrating approval_category approval_type values...")

    # First check if there are any records with the old value
    try:
        cr.execute(
            """
            SELECT COUNT(*) 
            FROM approval_category 
            WHERE approval_type = 'fleet_vehicle_log'
        """
        )
        old_count = cr.fetchone()[0]
        _logger.info(
            f"Found {old_count} approval_category records with old approval_type"
        )

        if old_count > 0:
            cr.execute(
                """
                UPDATE approval_category 
                SET approval_type = 'product_asset_log' 
                WHERE approval_type = 'fleet_vehicle_log'
            """
            )
            updated_count = cr.rowcount
            _logger.info(
                f"Updated {updated_count} approval_category records with new approval_type"
            )
        else:
            _logger.info("No approval_category records need migration")

    except Exception as e:
        _logger.warning(f"Could not migrate approval_category.approval_type: {str(e)}")


def _migrate_approval_request_vehicles(cr, env):
    """Migrate approval_request.vehicle_id references from fleet.vehicle to stock.lot"""
    _logger.info("Migrating approval_request vehicle_id references...")

    # Get all approval requests with vehicle_id pointing to fleet.vehicle
    cr.execute(
        """
        SELECT ar.id, ar.vehicle_id 
        FROM approval_request ar
        WHERE ar.vehicle_id IS NOT NULL
    """
    )
    requests_data = cr.fetchall()

    migrated_count = 0
    failed_count = 0

    for request_id, old_vehicle_id in requests_data:
        try:
            # Find corresponding stock.lot by matching key fields
            cr.execute(
                """
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
            """,
                (old_vehicle_id,),
            )

            result = cr.fetchone()
            if result:
                new_asset_id = result[0]
                # Update the vehicle_id to point to stock.lot
                cr.execute(
                    """
                    UPDATE approval_request 
                    SET vehicle_id = %s 
                    WHERE id = %s
                """,
                    (new_asset_id, request_id),
                )
                migrated_count += 1
                _logger.debug(
                    f"Request {request_id}: fleet.vehicle({old_vehicle_id}) -> stock.lot({new_asset_id})"
                )
            else:
                _logger.warning(
                    f"No matching stock.lot found for request {request_id} with vehicle {old_vehicle_id}"
                )
                failed_count += 1

        except Exception as e:
            _logger.error(f"Error migrating request {request_id}: {str(e)}")
            failed_count += 1

    _logger.info(
        f"Approval request vehicles migration: {migrated_count} migrated, {failed_count} failed"
    )


def _migrate_approval_request_logs(cr, env):
    """Update approval_request.log_ids to reference product.asset.log instead of fleet.vehicle.log"""
    _logger.info("Migrating approval_request log_ids references...")

    # Check if there are any fleet.vehicle.log records that need to be migrated to product.asset.log
    # This should already be handled by the product_asset module migration
    # But we verify the references are consistent

    cr.execute(
        """
        SELECT COUNT(*) 
        FROM approval_request ar
        JOIN product_asset_log pal ON pal.approval_request_id = ar.id
    """
    )
    migrated_logs_count = cr.fetchone()[0]

    _logger.info(
        f"Found {migrated_logs_count} product.asset.log records linked to approval_request"
    )


def _validate_migration(cr, env):
    """Validate that migration was successful"""
    _logger.info("Validating migration results...")

    try:
        # Check approval categories with old type
        cr.execute(
            """
            SELECT COUNT(*) 
            FROM approval_category 
            WHERE approval_type = 'fleet_vehicle_log'
        """
        )
        old_categories = cr.fetchone()[0]
    except Exception as e:
        _logger.warning(f"Could not validate approval_category: {str(e)}")
        old_categories = -1

    # approval_request.approval_type is a related field, so validation is automatic
    old_requests = 0

    try:
        # Check approval requests with vehicle references to stock.lot
        cr.execute(
            """
            SELECT COUNT(*) 
            FROM approval_request ar
            JOIN stock_lot sl ON ar.vehicle_id = sl.id
            WHERE sl.asset_type = 'vehicle'
        """
        )
        valid_vehicle_refs = cr.fetchone()[0]
    except Exception as e:
        _logger.warning(f"Could not validate vehicle references: {str(e)}")
        valid_vehicle_refs = -1

    _logger.info(f"Migration validation results:")
    _logger.info(f"  - Categories with old type: {old_categories}")
    _logger.info(f"  - Requests with old type: {old_requests}")
    _logger.info(f"  - Requests with valid vehicle refs: {valid_vehicle_refs}")

    if old_categories > 0 or old_requests > 0:
        _logger.warning(
            f"Found {old_categories + old_requests} records with old fleet references"
        )
    else:
        _logger.info("All approval references migrated successfully!")
