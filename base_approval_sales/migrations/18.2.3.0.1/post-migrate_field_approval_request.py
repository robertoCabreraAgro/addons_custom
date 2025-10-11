"""
Migration script to ensure approval_request_ref field is properly migrated to approval_request_id
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migrate approval_request_ref to approval_request_id if needed."""
    _logger.info("Starting migration of approval_request fields in sale.order")

    try:
        # Check if old column exists
        cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'sale_order'
            AND column_name = 'approval_request_ref'
        """)
        old_column_exists = bool(cr.fetchone())

        # Check if new column exists
        cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'sale_order'
            AND column_name = 'approval_request_id'
        """)
        new_column_exists = bool(cr.fetchone())

        _logger.info(f"Old column (approval_request_ref) exists: {old_column_exists}")
        _logger.info(f"New column (approval_request_id) exists: {new_column_exists}")

        if old_column_exists and new_column_exists:
            # Migrate data from old column to new column
            _logger.info("Migrating data from approval_request_ref to approval_request_id")
            cr.execute("""
                UPDATE sale_order
                SET approval_request_id = CASE
                    WHEN approval_request_ref ~ '^[0-9]+$'
                    THEN approval_request_ref::integer
                    ELSE NULL
                END
                WHERE approval_request_ref IS NOT NULL
                AND approval_request_id IS NULL
            """)
            migrated_count = cr.rowcount
            _logger.info(f"Migrated {migrated_count} records")

            # Drop old column
            _logger.info("Dropping old approval_request_ref column")
            cr.execute("ALTER TABLE sale_order DROP COLUMN IF EXISTS approval_request_ref")

        elif old_column_exists and not new_column_exists:
            # Rename old column to new column name
            _logger.info("Renaming approval_request_ref to approval_request_id")
            cr.execute("""
                ALTER TABLE sale_order
                RENAME COLUMN approval_request_ref TO approval_request_id
            """)

            # Update column type if needed
            cr.execute("""
                ALTER TABLE sale_order
                ALTER COLUMN approval_request_id TYPE integer
                USING CASE
                    WHEN approval_request_id ~ '^[0-9]+$'
                    THEN approval_request_id::integer
                    ELSE NULL
                END
            """)

        _logger.info("Migration completed successfully")

    except Exception as e:
        _logger.error(f"Migration failed: {e}")
        raise