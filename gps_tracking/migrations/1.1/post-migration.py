import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    _logger.info("Starting migration to add composite index to gps.tracking.point.")

    # This single composite index is more efficient for the report query
    # than two separate indexes.
    cr.execute(
        """
            CREATE INDEX IF NOT EXISTS
                gps_tracking_point_driver_timestamp_idx
                ON gps_tracking_point (driver_id, timestamp);
        """
    )

    _logger.info("Finished adding composite index.")
