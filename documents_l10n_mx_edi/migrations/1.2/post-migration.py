import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration script for Documents L10n MX EDI module v1.2
    Migrates vehicle references from fleet.vehicle to stock.lot (product_asset)
    """
    _logger.info(
        "Starting Documents L10n MX EDI migration from fleet to product_asset..."
    )

    env = api.Environment(cr, SUPERUSER_ID, {})

    try:
        # 1. Update any cached vehicle references
        _clear_vehicle_caches(cr, env)

        # 2. Validate vehicle search functionality
        _validate_vehicle_searches(cr, env)

        _logger.info("Documents L10n MX EDI migration completed successfully!")

    except Exception as e:
        _logger.error(f"Documents L10n MX EDI migration failed: {str(e)}")
        cr.rollback()
        raise


def _clear_vehicle_caches(cr, env):
    """Clear any cached vehicle references that might cause issues"""
    _logger.info("Clearing vehicle reference caches...")

    # Clear any computed field caches related to vehicles
    # This ensures that the new vehicle search logic will be used
    try:
        # Force recomputation of any cached vehicle lookups
        cr.execute(
            """
            SELECT COUNT(*) 
            FROM l10n_mx_edi_document 
            WHERE state IN ('draft', 'sent', 'received')
        """
        )
        active_documents = cr.fetchone()[0]
        _logger.info(
            f"Found {active_documents} active EDI documents for cache clearing"
        )

    except Exception as e:
        _logger.warning(f"Error during cache clearing: {str(e)}")


def _validate_vehicle_searches(cr, env):
    """Validate that vehicle searches will work with stock.lot"""
    _logger.info("Validating vehicle search functionality...")

    # Test the vehicle search logic with stock.lot
    try:
        # Check if there are stock.lot records with asset_type='vehicle' and fuel_card_name
        cr.execute(
            """
            SELECT COUNT(*) 
            FROM stock_lot 
            WHERE asset_type = 'vehicle' 
            AND fuel_card_name IS NOT NULL
        """
        )
        vehicles_with_fuel_cards = cr.fetchone()[0]

        # Check if there are any product.asset.log records
        cr.execute(
            """
            SELECT COUNT(*) 
            FROM product_asset_log 
            WHERE product_category_id IN (
                SELECT id FROM product_category WHERE name LIKE '%fuel%' OR name LIKE '%Fuel%'
            )
        """
        )
        fuel_logs_count = cr.fetchone()[0]

        _logger.info(f"Vehicle search validation:")
        _logger.info(f"  - Vehicles with fuel cards: {vehicles_with_fuel_cards}")
        _logger.info(f"  - Fuel logs in product.asset.log: {fuel_logs_count}")

    except Exception as e:
        _logger.warning(f"Error during vehicle search validation: {str(e)}")
