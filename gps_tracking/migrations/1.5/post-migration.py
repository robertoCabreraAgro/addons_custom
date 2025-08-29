import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration script for GPS Tracking module v1.5
    Migrates references from fleet.vehicle to stock.lot (product_asset)
    """
    _logger.info("Starting GPS Tracking migration from fleet to product_asset...")

    env = api.Environment(cr, SUPERUSER_ID, {})

    try:
        # 1. Update gps_tracking_device references
        _migrate_gps_device_references(cr, env)

        # 2. Update gps_tracking_point references
        _migrate_gps_point_references(cr, env)

        # 3. Update asset_loan_report SQL view
        _migrate_report_views(cr, env)

        # 4. Validate migration success
        _validate_migration(cr, env)

        # 5. Create performance indexes for GPS queries
        _create_gps_indexes(cr, env)

        _logger.info("GPS Tracking migration completed successfully!")

    except Exception as e:
        _logger.error(f"GPS Tracking migration failed: {str(e)}")
        cr.rollback()
        raise


def _migrate_gps_device_references(cr, env):
    """Migrate gps.tracking.device.vehicle_id references to asset_id"""
    _logger.info("Migrating GPS device references from vehicle_id to asset_id...")

    # Get all devices with vehicle_id (old column) pointing to fleet.vehicle
    cr.execute(
        """
        SELECT id, vehicle_id 
        FROM gps_tracking_device 
        WHERE vehicle_id IS NOT NULL
    """
    )
    devices_data = cr.fetchall()

    migrated_count = 0
    failed_count = 0

    for device_id, old_vehicle_id in devices_data:
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
                # Update the new asset_id column
                cr.execute(
                    """
                    UPDATE gps_tracking_device 
                    SET asset_id = %s 
                    WHERE id = %s
                """,
                    (new_asset_id, device_id),
                )
                migrated_count += 1
                _logger.debug(
                    f"Device {device_id}: fleet.vehicle({old_vehicle_id}) -> stock.lot({new_asset_id})"
                )
            else:
                _logger.warning(
                    f"No matching stock.lot found for device {device_id} with vehicle {old_vehicle_id}"
                )
                failed_count += 1

        except Exception as e:
            _logger.error(f"Error migrating device {device_id}: {str(e)}")
            failed_count += 1

    # After migration, clear the old vehicle_id column to avoid confusion
    cr.execute(
        """
        UPDATE gps_tracking_device 
        SET vehicle_id = NULL 
        WHERE vehicle_id IS NOT NULL
    """
    )
    cleared_count = cr.rowcount

    _logger.info(
        f"GPS devices migration: {migrated_count} migrated, {failed_count} failed, {cleared_count} old references cleared"
    )


def _migrate_gps_point_references(cr, env):
    """Migrate gps.tracking.point asset references"""
    _logger.info("Migrating GPS point references from vehicle_id to asset_id...")

    # First, get total count for progress tracking
    cr.execute(
        """
        SELECT COUNT(*) 
        FROM gps_tracking_point 
        WHERE vehicle_id IS NOT NULL
    """
    )
    total_points = cr.fetchone()[0]
    _logger.info(f"Total GPS points to migrate: {total_points}")

    if total_points == 0:
        _logger.info("No GPS points to migrate")
        return

    # Create a mapping table of fleet_vehicle.id -> stock_lot.id for faster lookups
    _logger.info("Creating fleet-to-asset mapping table...")
    cr.execute(
        """
        CREATE TEMPORARY TABLE temp_vehicle_mapping AS (
            SELECT DISTINCT 
                fv.id as fleet_vehicle_id,
                sl.id as stock_lot_id
            FROM fleet_vehicle fv
            JOIN stock_lot sl ON (
                sl.license_plate = fv.license_plate 
                OR (sl.vin_sn = fv.vin_sn AND sl.vin_sn IS NOT NULL)
                OR (sl.name = fv.name)
            )
            WHERE sl.asset_type = 'vehicle'
        )
    """
    )
    mapping_count = cr.rowcount
    _logger.info(f"Created mapping for {mapping_count} fleet vehicles to assets")

    # Bulk update GPS points using the mapping table
    _logger.info("Performing bulk update of GPS points...")
    cr.execute(
        """
        UPDATE gps_tracking_point 
        SET asset_id = tvm.stock_lot_id
        FROM temp_vehicle_mapping tvm
        WHERE gps_tracking_point.vehicle_id = tvm.fleet_vehicle_id
        AND gps_tracking_point.vehicle_id IS NOT NULL
    """
    )
    migrated_count = cr.rowcount

    # Count failed migrations (points without matching assets)
    cr.execute(
        """
        SELECT COUNT(*) 
        FROM gps_tracking_point gtp
        WHERE gtp.vehicle_id IS NOT NULL 
        AND gtp.asset_id IS NULL
    """
    )
    failed_count = cr.fetchone()[0]

    if failed_count > 0:
        _logger.warning(f"Found {failed_count} GPS points without matching assets")
        # Log some examples for debugging
        cr.execute(
            """
            SELECT DISTINCT gtp.vehicle_id, fv.name, fv.license_plate
            FROM gps_tracking_point gtp
            LEFT JOIN fleet_vehicle fv ON gtp.vehicle_id = fv.id
            WHERE gtp.vehicle_id IS NOT NULL 
            AND gtp.asset_id IS NULL
            LIMIT 5
        """
        )
        examples = cr.fetchall()
        for vehicle_id, name, license_plate in examples:
            _logger.warning(
                f"  - Vehicle {vehicle_id}: {name} ({license_plate}) has no matching asset"
            )

    # Clear the old vehicle_id column
    _logger.info("Clearing old vehicle_id references...")
    cr.execute(
        """
        UPDATE gps_tracking_point 
        SET vehicle_id = NULL 
        WHERE vehicle_id IS NOT NULL
    """
    )
    cleared_count = cr.rowcount

    # Drop the temporary mapping table
    cr.execute("DROP TABLE IF EXISTS temp_vehicle_mapping")

    _logger.info(
        f"GPS points migration: {migrated_count} migrated, {failed_count} failed, {cleared_count} old references cleared"
    )


def _migrate_report_views(cr, env):
    """Update SQL views to use stock_lot instead of fleet_vehicle"""
    _logger.info("Migrating report views...")

    try:
        # Drop and recreate asset_loan_report view
        cr.execute("DROP VIEW IF EXISTS asset_loan_report")
        cr.execute("DROP VIEW IF EXISTS fleet_vehicle_loan_report")

        # Recreate the view with updated query (stock_lot instead of fleet_vehicle)
        cr.execute(
            """
            CREATE OR REPLACE VIEW asset_loan_report AS (
                WITH
                -- Step 1: Define trip segments.
                    TripSegments AS (
                        SELECT
                            a.employee_id,
                            a.check_in AS start_time,
                            a.check_out AS end_time,
                            'Dentro del trabajo' AS work_hours_status
                        FROM
                            hr_attendance AS a
                        JOIN
                            hr_employee AS he
                            ON a.employee_id = he.id
                        WHERE
                            a.check_out IS NOT NULL
                            AND he.enable_vehicle_loan = TRUE
                        UNION ALL
                        SELECT
                            a.employee_id,
                            a.check_out AS start_time,
                            LEAD(a.check_in) OVER (
                                PARTITION BY a.employee_id
                                ORDER BY a.check_in
                            ) AS end_time,
                            'Fuera del trabajo' AS work_hours_status
                        FROM
                            hr_attendance AS a
                        JOIN
                            hr_employee AS he
                            ON a.employee_id = he.id
                        WHERE
                            he.enable_vehicle_loan = TRUE
                    ),
                -- Step 2: For each trip segment, find the ID of the nearest start and end GPS point.
                    TripDataPoints AS (
                        SELECT
                            ts.employee_id,
                            ts.start_time,
                            ts.end_time,
                            ts.work_hours_status,
                            he.name AS username,
                        -- Find the single closest GPS point ID at the START of the trip
                            (
                                SELECT
                                    gtp.id
                                FROM
                                    gps_tracking_point AS gtp
                                WHERE
                                    gtp.driver_id = ts.employee_id
                                    AND gtp."timestamp" BETWEEN
                                        (ts.start_time - interval '2 hours')
                                        AND (ts.start_time + interval '2 hours')
                                ORDER BY
                                    ABS(EXTRACT(EPOCH FROM (gtp."timestamp" - ts.start_time)))
                                LIMIT 1
                            ) AS start_point_id
                        FROM
                            TripSegments AS ts
                        JOIN
                            hr_employee AS he
                            ON ts.employee_id = he.id
                        WHERE
                            ts.end_time IS NOT NULL
                    ),
                -- Step 3: Get start point details and find matching end point for the same vehicle
                    TripDataWithVehicle AS (
                        SELECT
                            tdp.*,
                            start_point.id AS start_point_id_final,
                            start_point.device_id AS device_id,
                            -- Find the closest GPS point at the END of the trip for the SAME DEVICE/VEHICLE
                            (
                                SELECT
                                    gtp.id
                                FROM
                                    gps_tracking_point AS gtp
                                WHERE
                                    gtp.device_id = start_point.device_id  -- Same device as start point
                                    AND gtp."timestamp" BETWEEN
                                        (tdp.end_time - interval '2 hours')
                                        AND (tdp.end_time + interval '2 hours')
                                ORDER BY
                                    ABS(EXTRACT(EPOCH FROM (gtp."timestamp" - tdp.end_time)))
                                LIMIT 1
                            ) AS end_point_id
                        FROM
                            TripDataPoints AS tdp
                        LEFT JOIN
                            gps_tracking_point AS start_point
                            ON tdp.start_point_id = start_point.id
                    )
                -- Step 4: Final report - join the point IDs to get all details.
                SELECT
                    (row_number() OVER ())::integer AS id,
                    tdv.username,
                    sl.name AS vehiculo,
                    tdv.work_hours_status,
                    start_point.real_odometer AS odometer_start,
                    end_point.real_odometer AS odometer_end,
                    tdv.start_time AS date_start,
                    CASE EXTRACT(DOW FROM tdv.start_time AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')
                        WHEN 0 THEN 'Domingo'
                        WHEN 1 THEN 'Lunes'
                        WHEN 2 THEN 'Martes'
                        WHEN 3 THEN 'Miércoles'
                        WHEN 4 THEN 'Jueves'
                        WHEN 5 THEN 'Viernes'
                        WHEN 6 THEN 'Sábado'
                    END AS weekday_start,
                    tdv.end_time AS date_end,
                    CASE EXTRACT(DOW FROM tdv.end_time AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')
                        WHEN 0 THEN 'Domingo'
                        WHEN 1 THEN 'Lunes'
                        WHEN 2 THEN 'Martes'
                        WHEN 3 THEN 'Miércoles'
                        WHEN 4 THEN 'Jueves'
                        WHEN 5 THEN 'Viernes'
                        WHEN 6 THEN 'Sábado'
                    END AS weekday_end,
                    CASE
                        WHEN end_point.real_odometer - start_point.real_odometer < 0 THEN 0
                        ELSE COALESCE(end_point.real_odometer - start_point.real_odometer, 0)
                    END AS distance
                FROM
                    TripDataWithVehicle AS tdv
                LEFT JOIN
                    gps_tracking_point AS start_point
                    ON tdv.start_point_id_final = start_point.id
                LEFT JOIN
                    gps_tracking_point AS end_point
                    ON tdv.end_point_id = end_point.id
                LEFT JOIN
                    gps_tracking_device AS gtd
                    ON tdv.device_id = gtd.id
                LEFT JOIN
                    stock_lot AS sl
                    ON gtd.asset_id = sl.id
                WHERE
                    tdv.start_point_id IS NOT NULL
                ORDER BY
                    tdv.start_time
            )
        """
        )

        _logger.info("Report views migrated successfully")

    except Exception as e:
        _logger.error(f"Error migrating report views: {str(e)}")
        raise


def _validate_migration(cr, env):
    """Validate that migration was successful"""
    _logger.info("Validating migration results...")

    # Check devices without valid vehicle references
    cr.execute(
        """
        SELECT COUNT(*) 
        FROM gps_tracking_device gtd
        LEFT JOIN stock_lot sl ON gtd.vehicle_id = sl.id
        WHERE gtd.vehicle_id IS NOT NULL AND sl.id IS NULL
    """
    )
    orphaned_devices = cr.fetchone()[0]

    # Check total devices migrated
    cr.execute(
        """
        SELECT COUNT(*) 
        FROM gps_tracking_device 
        WHERE vehicle_id IS NOT NULL
    """
    )
    total_devices_with_vehicle = cr.fetchone()[0]

    # Check total points with vehicle
    cr.execute(
        """
        SELECT COUNT(*)
        FROM gps_tracking_point
        WHERE vehicle_id IS NOT NULL
    """
    )
    total_points_with_vehicle = cr.fetchone()[0]

    _logger.info(f"Migration validation results:")
    _logger.info(f"  - Devices with vehicle: {total_devices_with_vehicle}")
    _logger.info(f"  - Points with vehicle: {total_points_with_vehicle}")
    _logger.info(f"  - Orphaned devices: {orphaned_devices}")

    if orphaned_devices > 0:
        _logger.warning(
            f"Found {orphaned_devices} devices with invalid vehicle references"
        )
    else:
        _logger.info("All device references are valid!")


def _create_gps_indexes(cr, env):
    """Create critical indexes to optimize GPS tracking point queries"""
    _logger.info("Creating GPS performance indexes...")

    try:
        # Index for driver_id and timestamp queries (most critical for asset loan report)
        _logger.info("Creating driver + timestamp index...")
        cr.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gps_tracking_point_driver_timestamp 
            ON gps_tracking_point (driver_id, timestamp)
        """
        )

        # Index for device_id and timestamp queries (most critical for asset loan report)
        _logger.info("Creating device + timestamp index...")
        cr.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gps_tracking_point_device_timestamp 
            ON gps_tracking_point (device_id, timestamp)
        """
        )

        # B-tree index for timestamp range queries (optimizes BETWEEN operations)
        _logger.info("Creating timestamp btree index...")
        cr.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gps_tracking_point_timestamp_btree 
            ON gps_tracking_point USING btree (timestamp)
        """
        )

        _logger.info("GPS performance indexes created successfully")

    except Exception as e:
        _logger.error(f"Error creating GPS indexes: {str(e)}")
        # Don't raise - indexes are performance optimization, not critical
