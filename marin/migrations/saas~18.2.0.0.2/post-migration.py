import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    migrate_reconditioned_data(cr)


def migrate_reconditioned_data(cr):
    """Migrate existing reconditioned lots data to original_expiration_date field."""
    cr.execute(
        """
        UPDATE
            stock_lot
        SET
            original_expiration_date = expiration_date
        WHERE
            original_expiration_date IS NULL
            AND expiration_date IS NOT NULL
        """
    )
    non_reconditioned_updated = cr.rowcount
    _logger.info("Updated %s non-reconditioned lots with original_expiration_date", non_reconditioned_updated)
