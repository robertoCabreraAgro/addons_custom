import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migration script for Marin module v18.2.0.0.5
    Migrates production type from x_type to production_type field in mrp.bom
    """
    if not version:
        return

    _logger.info("Starting production_type migration from x_type...")

    api.Environment(cr, SUPERUSER_ID, {})

    try:
        migrate_bom_production_type(cr, version)
        migrate_mrp_production_type(cr, version)
        _logger.info("Production type migration completed successfully!")

    except Exception as e:
        _logger.error("Production type migration failed: %s", str(e))
        cr.rollback()
        raise


def migrate_bom_production_type(cr, version):
    """Migrate x_type field to production_type field in mrp_bom"""
    if not version:
        return

    _logger.info("Starting x_type to production_type migration...")

    # Value mapping from old x_type to new production_type
    value_mapping = {
        "formulate": "formulated",
        "reformulate": "reformulated",
        "refill": "packaged",
    }

    total_migrated = 0

    # Update records with mapped values
    for old_value, new_value in value_mapping.items():
        cr.execute(
            """
            UPDATE
                mrp_bom
            SET
                production_type = %s
            WHERE
                x_type = %s
                AND production_type IS NULL
            """,
            (new_value, old_value),
        )
        migrated_count = cr.rowcount
        total_migrated += migrated_count
        if migrated_count > 0:
            _logger.info(
                "Migrated %d records from '%s' to '%s'",
                migrated_count,
                old_value,
                new_value,
            )

    _logger.info(
        "Migration x_type -> production_type completed: %d records migrated",
        total_migrated,
    )


def migrate_mrp_production_type(cr, version):
    """Update production_type in mrp_production from related bom_id.production_type"""
    if not version:
        return

    _logger.info("Starting mrp_production production_type update from BOM...")

    # Update mrp_production.production_type from bom_id.production_type
    cr.execute(
        """
        UPDATE
            mrp_production
        SET
            production_type = bom.production_type
        FROM
            mrp_bom bom
        WHERE
            mrp_production.bom_id = bom.id
            AND bom.production_type IS NOT NULL
            AND (mrp_production.production_type IS NULL 
                OR mrp_production.production_type != bom.production_type)
        """
    )

    updated_count = cr.rowcount
    _logger.info(
        "Updated production_type in mrp_production: %d records updated", updated_count
    )
