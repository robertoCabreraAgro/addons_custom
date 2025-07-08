import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    _logger.info("Starting PRE-migration to add and populate driver_id on gps.tracking.point.")

    # Step 1: Manually add the column to the table if it doesn't exist.
    cr.execute(
        """
            ALTER TABLE
                gps_tracking_point
            ADD COLUMN IF NOT EXISTS
                driver_id INTEGER;
        """
    )
    _logger.info("Step 1/3: Column gps_tracking_point.driver_id created or already exists.")

    # Step 2: Add the foreign key constraint that Odoo would normally create.
    cr.execute(
        """
            SELECT
                1
            FROM
                pg_constraint
            WHERE
                conname = 'gps_tracking_point_driver_id_fkey';
        """
    )
    if not cr.fetchone():
        cr.execute(
            """
                ALTER TABLE
                    gps_tracking_point
                ADD CONSTRAINT
                    gps_tracking_point_driver_id_fkey
                    FOREIGN KEY (driver_id)
                    REFERENCES hr_employee (id)
                    ON DELETE SET NULL;
            """
        )
        _logger.info("Step 2/3: Foreign key constraint for driver_id has been created.")
    else:
        _logger.info("Step 2/3: Foreign key constraint for driver_id already exists, skipping.")

    # Step 3: Now that the column exists, populate it using the efficient query.
    cr.execute(
        """
            UPDATE
                gps_tracking_point gtp
            SET
                driver_id = fv.driver_id
            FROM
                fleet_vehicle fv
            WHERE
                gtp.vehicle_id = fv.id
                AND gtp.driver_id IS NULL;
        """
    )
    _logger.info("Step 3/3: Finished populating driver_id for existing records.")
