import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration script for Product Asset module v1.1
    Updates existing product.asset.log records to use the new product references
    that were moved from 'marin' module to 'product_asset' module.
    """
    _logger.info(
        "Starting Product Asset module migration - updating product references in logs..."
    )

    env = api.Environment(cr, SUPERUSER_ID, {})

    try:
        # 1. Update product_category_id references in product.asset.log records
        _migrate_log_product_categories(cr, env)

        # 2. Update product_id references in product.asset.log records
        _migrate_log_products(cr, env)

        # 3. Validate migration success
        _validate_migration(cr, env)

        _logger.info("Product Asset module migration completed successfully!")

    except Exception as e:
        _logger.error(f"Product Asset module migration failed: {str(e)}")
        cr.rollback()
        raise


def _migrate_log_product_categories(cr, env):
    """Update product_category_id references from marin to product_asset module."""
    _logger.info("Migrating product.asset.log product_category_id references...")

    # Dictionary mapping old marin references to new product_asset references
    category_mappings = {
        'fuel': ('marin.product_category_fuel', 'product_asset.product_category_fuel'),
        'highway_toll': ('marin.product_category_highway_toll', 'product_asset.product_category_highway_toll'),
    }

    for category_type, (old_xmlid, new_xmlid) in category_mappings.items():
        try:
            # Get the old category ID if it exists
            cr.execute("""
                SELECT res_id 
                FROM ir_model_data 
                WHERE module = 'marin' 
                AND name = %s
                AND model = 'product.category'
            """, (old_xmlid.split('.')[-1],))
            
            old_result = cr.fetchone()
            
            # Get the new category ID
            cr.execute("""
                SELECT res_id 
                FROM ir_model_data 
                WHERE module = 'product_asset' 
                AND name = %s
                AND model = 'product.category'
            """, (new_xmlid.split('.')[-1],))
            
            new_result = cr.fetchone()
            
            if old_result and new_result:
                old_category_id = old_result[0]
                new_category_id = new_result[0]
                
                # Check how many logs need to be updated
                cr.execute("""
                    SELECT COUNT(*) 
                    FROM product_asset_log 
                    WHERE product_category_id = %s
                """, (old_category_id,))
                
                count_to_update = cr.fetchone()[0]
                
                if count_to_update > 0:
                    # Update the logs
                    cr.execute("""
                        UPDATE product_asset_log 
                        SET product_category_id = %s 
                        WHERE product_category_id = %s
                    """, (new_category_id, old_category_id))
                    
                    updated_count = cr.rowcount
                    _logger.info(
                        f"Updated {updated_count} product.asset.log records with {category_type} category"
                    )
                else:
                    _logger.info(f"No logs found with old {category_type} category")
            elif not old_result:
                _logger.info(f"Old {category_type} category not found - might already be migrated")
            elif not new_result:
                _logger.warning(f"New {category_type} category not found in product_asset module")
                
        except Exception as e:
            _logger.error(f"Error migrating {category_type} category: {str(e)}")


def _migrate_log_products(cr, env):
    """Update product_id references from marin to product_asset module."""
    _logger.info("Migrating product.asset.log product_id references...")

    # Dictionary mapping old marin references to new product_asset references
    product_mappings = {
        'fuel_debit': ('marin.product_product_fuel_debit', 'product_asset.product_product_fuel_debit'),
        'fuel_credit': ('marin.product_product_fuel_credit', 'product_asset.product_product_fuel_credit'),
        'highway_debit': ('marin.product_product_highway_debit', 'product_asset.product_product_highway_debit'),
        'highway_credit': ('marin.product_product_highway_credit', 'product_asset.product_product_highway_credit'),
    }

    for product_type, (old_xmlid, new_xmlid) in product_mappings.items():
        try:
            # Get the old product ID if it exists
            cr.execute("""
                SELECT res_id 
                FROM ir_model_data 
                WHERE module = 'marin' 
                AND name = %s
                AND model = 'product.product'
            """, (old_xmlid.split('.')[-1],))
            
            old_result = cr.fetchone()
            
            # Get the new product ID
            cr.execute("""
                SELECT res_id 
                FROM ir_model_data 
                WHERE module = 'product_asset' 
                AND name = %s
                AND model = 'product.product'
            """, (new_xmlid.split('.')[-1],))
            
            new_result = cr.fetchone()
            
            if old_result and new_result:
                old_product_id = old_result[0]
                new_product_id = new_result[0]
                
                # Check how many logs need to be updated
                cr.execute("""
                    SELECT COUNT(*) 
                    FROM product_asset_log 
                    WHERE product_id = %s
                """, (old_product_id,))
                
                count_to_update = cr.fetchone()[0]
                
                if count_to_update > 0:
                    # Update the logs
                    cr.execute("""
                        UPDATE product_asset_log 
                        SET product_id = %s 
                        WHERE product_id = %s
                    """, (new_product_id, old_product_id))
                    
                    updated_count = cr.rowcount
                    _logger.info(
                        f"Updated {updated_count} product.asset.log records with {product_type} product"
                    )
                else:
                    _logger.info(f"No logs found with old {product_type} product")
            elif not old_result:
                _logger.info(f"Old {product_type} product not found - might already be migrated")
            elif not new_result:
                _logger.warning(f"New {product_type} product not found in product_asset module")
                
        except Exception as e:
            _logger.error(f"Error migrating {product_type} product: {str(e)}")


def _validate_migration(cr, env):
    """Validate that migration was successful."""
    _logger.info("Validating migration results...")

    try:
        # Check for logs still referencing old marin categories
        cr.execute("""
            SELECT COUNT(*) 
            FROM product_asset_log pal
            JOIN product_category pc ON pal.product_category_id = pc.id
            JOIN ir_model_data imd ON (imd.res_id = pc.id AND imd.model = 'product.category')
            WHERE imd.module = 'marin' 
            AND imd.name IN ('product_category_fuel', 'product_category_highway_toll')
        """)
        
        old_category_refs = cr.fetchone()[0]
        
        # Check for logs still referencing old marin products
        cr.execute("""
            SELECT COUNT(*) 
            FROM product_asset_log pal
            JOIN product_product pp ON pal.product_id = pp.id
            JOIN ir_model_data imd ON (imd.res_id = pp.id AND imd.model = 'product.product')
            WHERE imd.module = 'marin' 
            AND imd.name IN ('product_product_fuel_debit', 'product_product_fuel_credit', 
                           'product_product_highway_debit', 'product_product_highway_credit')
        """)
        
        old_product_refs = cr.fetchone()[0]
        
        # Check for logs now referencing new product_asset categories/products
        cr.execute("""
            SELECT COUNT(*) 
            FROM product_asset_log pal
            JOIN product_category pc ON pal.product_category_id = pc.id
            JOIN ir_model_data imd ON (imd.res_id = pc.id AND imd.model = 'product.category')
            WHERE imd.module = 'product_asset' 
            AND imd.name IN ('product_category_fuel', 'product_category_highway_toll')
        """)
        
        new_category_refs = cr.fetchone()[0]
        
        cr.execute("""
            SELECT COUNT(*) 
            FROM product_asset_log pal
            JOIN product_product pp ON pal.product_id = pp.id
            JOIN ir_model_data imd ON (imd.res_id = pp.id AND imd.model = 'product.product')
            WHERE imd.module = 'product_asset' 
            AND imd.name IN ('product_product_fuel_debit', 'product_product_fuel_credit', 
                           'product_product_highway_debit', 'product_product_highway_credit')
        """)
        
        new_product_refs = cr.fetchone()[0]
        
        _logger.info("Migration validation results:")
        _logger.info(f"  - Logs with old category references: {old_category_refs}")
        _logger.info(f"  - Logs with old product references: {old_product_refs}")
        _logger.info(f"  - Logs with new category references: {new_category_refs}")
        _logger.info(f"  - Logs with new product references: {new_product_refs}")
        
        if old_category_refs > 0 or old_product_refs > 0:
            _logger.warning(
                f"Found {old_category_refs + old_product_refs} logs with old marin references"
            )
        else:
            _logger.info("All product.asset.log references migrated successfully!")
            
    except Exception as e:
        _logger.warning(f"Could not complete migration validation: {str(e)}")