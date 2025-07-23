"""
Post-migration script for version 1.2
Adds indexes to optimize fleet vehicle loan report performance
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add indexes to optimize vehicle loan report queries
    """
    _logger.info("Creating indexes for fleet vehicle loan report optimization")

    # Index for timestamp-based searches on gps_tracking_point
    # This helps with the time range queries in the report
    cr.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_gps_tracking_point_timestamp_driver
            ON gps_tracking_point(driver_id, timestamp);
        """
    )

    # Index for device-based timestamp searches
    # This helps when finding end points for the same vehicle
    cr.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_gps_tracking_point_device_timestamp
            ON gps_tracking_point(device_id, timestamp);
        """
    )

    # Composite index for the main query pattern
    cr.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_gps_tracking_point_composite
            ON gps_tracking_point(driver_id, device_id, timestamp);
        """
    )

    # Index on hr_attendance for the vehicle loan queries
    cr.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_hr_attendance_employee_checkin
            ON hr_attendance(employee_id, check_in);
        """
    )

    cr.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_hr_attendance_employee_checkout
            ON hr_attendance(employee_id, check_out)
        WHERE
            check_out IS NOT NULL;
        """
    )

    # Index on hr_employee for the enable_vehicle_loan filter
    cr.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_hr_employee_vehicle_loan
            ON hr_employee(id)
        WHERE
        enable_vehicle_loan = TRUE;
        """
    )

    _logger.info("Indexes created successfully")
