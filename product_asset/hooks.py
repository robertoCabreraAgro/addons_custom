# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Post installation hook for product_asset module
    Migrates data from fleet module to product_asset
    """
    _logger.info("=== Starting Product Asset installation hook ===")
    
    cr = env.cr
    
    try:
        # Check if fleet module exists and has data
        if not _check_fleet_module_availability(env):
            _logger.info("Fleet module not found or no data to migrate. Skipping migration.")
            return
        
        # Reorganize partner IDs if needed (from original script)
        _reorganize_partner_ids(env)
        
        # Main migration: fleet -> product_asset
        _migrate_fleet_to_product_asset(env)
        
        # Validate migration results
        _validate_migration_results(env)
        
        _logger.info("=== Product Asset installation hook completed successfully ===")
        
    except Exception as e:
        _logger.error(f"Product Asset installation hook failed: {str(e)}")
        cr.rollback()
        raise UserError(f"Migration failed: {str(e)}")


def _check_fleet_module_availability(env):
    """Check if fleet module is installed and has data"""
    _logger.info("Checking fleet module availability...")
    
    cr = env.cr
    
    # Check if fleet module is installed
    cr.execute("""
        SELECT state 
        FROM ir_module_module 
        WHERE name = 'fleet'
    """)
    
    result = cr.fetchone()
    if not result or result[0] != 'installed':
        _logger.info("Fleet module is not installed")
        return False
    
    # Check if there's data to migrate
    cr.execute("SELECT COUNT(*) FROM fleet_vehicle WHERE active IN (true, false)")
    vehicle_count = cr.fetchone()[0]
    
    _logger.info(f"Found {vehicle_count} vehicles in fleet module")
    return vehicle_count > 0


def _reorganize_partner_ids(env):
    """Reorganize partner IDs to avoid conflicts (from original script)"""
    _logger.info("Reorganizing partner IDs to avoid conflicts...")
    
    cr = env.cr
    
    # Find partners that might conflict with product_asset data
    cr.execute("""
        SELECT COUNT(*) 
        FROM res_partner 
        WHERE id >= 8667
    """)
    
    partners_count = cr.fetchone()[0]
    if partners_count == 0:
        _logger.info("No partner ID reorganization needed")
        return
    
    _logger.info(f"Reorganizing {partners_count} partner IDs...")
    
    # Get partners to reorganize
    cr.execute("""
        SELECT id 
        FROM res_partner 
        WHERE id >= 8667 
        ORDER BY id ASC
    """)
    
    partners_data = cr.fetchall()
    start_id = 7
    reorganized_count = 0
    
    for (partner_id,) in partners_data:
        try:
            # Update partner ID
            cr.execute("UPDATE res_partner SET id = %s WHERE id = %s", (start_id, partner_id))
            
            # Update related records
            cr.execute("""
                UPDATE ir_model_data 
                SET res_id = %s 
                WHERE res_id = %s AND module = 'product_asset' AND model = 'res.partner'
            """, (start_id, partner_id))
            
            cr.execute("""
                UPDATE ir_attachment 
                SET res_id = %s 
                WHERE res_id = %s AND res_model = 'res.partner'
            """, (start_id, partner_id))
            
            start_id += 1
            reorganized_count += 1
            
        except Exception as e:
            _logger.error(f"Error reorganizing partner {partner_id}: {str(e)}")
            raise
    
    _logger.info(f"Reorganized {reorganized_count} partner IDs")


def _migrate_fleet_to_product_asset(env):
    """Main migration from fleet to product_asset"""
    _logger.info("Starting fleet to product_asset migration...")
    
    cr = env.cr
    
    # Group vehicles by model to create product templates
    cr.execute("""
        SELECT 
            fvm.id as model_id,
            fvm.name as model_name,
            array_agg(fv.id ORDER BY fv.id) as vehicle_ids
        FROM fleet_vehicle fv
        JOIN fleet_vehicle_model fvm ON fv.model_id = fvm.id
        WHERE fv.active IN (true, false)
        GROUP BY fvm.id, fvm.name
    """)
    
    models_data = cr.fetchall()
    _logger.info(f"Found {len(models_data)} vehicle models to migrate")
    
    migrated_vehicles = 0
    created_templates = 0
    
    for model_id, model_name, vehicle_ids in models_data:
        try:
            # Get model details from a representative vehicle
            cr.execute("""
                SELECT 
                    power, fuel_tank_capacity, doors, seats, 
                    fuel_efficiency, co2, model_year
                FROM fleet_vehicle 
                WHERE model_id = %s 
                ORDER BY id DESC 
                LIMIT 1
            """, (model_id,))
            
            vehicle_data = cr.fetchone()
            if not vehicle_data:
                continue
                
            power, fuel_tank_capacity, doors, seats, fuel_efficiency, co2, model_year = vehicle_data
            
            # Create product.template for this model
            template_vals = {
                'name': model_name,
                'asset_type': 'vehicle',
                'is_storable': True,
                'categ_id': env.ref('product_asset.product_category_vehicles').id,
                'power': power or 0,
                'fuel_tank_capacity': fuel_tank_capacity or 0,
                'doors': doors or 0,
                'seats': seats or 0,
                'fuel_efficiency_theoretical': fuel_efficiency or 0,
                'co2': co2 or 0,
            }
            
            product_template = env['product.template'].create(template_vals)
            created_templates += 1
            
            _logger.debug(f"Created product template: {model_name} (ID: {product_template.id})")
            
            # Create stock.lot for each vehicle of this model
            for vehicle_id in vehicle_ids:
                migrated_count = _migrate_single_vehicle(env, vehicle_id, product_template)
                migrated_vehicles += migrated_count
                
        except Exception as e:
            _logger.error(f"Error migrating model {model_name}: {str(e)}")
            raise
    
    _logger.info(f"Migration completed: {created_templates} templates, {migrated_vehicles} vehicles")



def _migrate_single_vehicle(env, vehicle_id, product_template):
    """Migrate a single vehicle to stock.lot"""
    
    cr = env.cr
    
    # Check which columns exist in fleet_vehicle table
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'fleet_vehicle'
    """)
    available_columns = [col[0] for col in cr.fetchall()]
    
    # Build query with only existing columns
    base_columns = ['name', 'license_plate', 'vin_sn', 'engine_sn', 'location', 
                   'model_year', 'trailer_hook', 'brand_new', 'driver_id', 'manager_id', 'active', 'company_id']
    optional_columns = ['account_prefix', 'acquisition_date', 'original_value',
                       'fuel_card_openning_balance', 'fuel_card_budget', 
                       'highway_pass_openning_balance', 'highway_pass_budget']
    
    # Only select columns that exist
    selected_columns = [col for col in base_columns if col in available_columns]
    selected_optional = [col for col in optional_columns if col in available_columns]
    all_columns = selected_columns + selected_optional
    
    # Get vehicle data
    query = f"SELECT {', '.join(all_columns)} FROM fleet_vehicle WHERE id = %s"
    cr.execute(query, (vehicle_id,))
    
    vehicle_data = cr.fetchone()
    if not vehicle_data:
        return 0
    
    # Create dictionary from column names and data
    vehicle_dict = dict(zip(all_columns, vehicle_data))
    
    # Extract values with defaults for missing columns
    name = vehicle_dict.get('name', f'Vehicle {vehicle_id}')
    license_plate = vehicle_dict.get('license_plate')
    vin_sn = vehicle_dict.get('vin_sn')
    engine_sn = vehicle_dict.get('engine_sn')
    location = vehicle_dict.get('location')
    model_year = vehicle_dict.get('model_year')
    trailer_hook = vehicle_dict.get('trailer_hook', False)
    brand_new = vehicle_dict.get('brand_new', True)
    account_prefix = vehicle_dict.get('account_prefix')
    acquisition_date = vehicle_dict.get('acquisition_date')
    original_value = vehicle_dict.get('original_value', 0)
    driver_id = vehicle_dict.get('driver_id')
    manager_id = vehicle_dict.get('manager_id')
    fuel_card_openning_balance = vehicle_dict.get('fuel_card_openning_balance', 0)
    fuel_card_budget = vehicle_dict.get('fuel_card_budget', 0)
    highway_pass_openning_balance = vehicle_dict.get('highway_pass_openning_balance', 0)
    highway_pass_budget = vehicle_dict.get('highway_pass_budget', 0)
    active = vehicle_dict.get('active', True)
    company_id = vehicle_dict.get('company_id')
    
    try:
        # Create stock.lot
        lot_vals = {
            'name': name,
            'product_id': product_template.product_variant_ids[0].id,
            'company_id': company_id,
            'operator_id': driver_id,
            'asset_manager_id': manager_id,
            'location': location,
            'model_year': model_year,
            'license_plate': license_plate,
            'vin_sn': vin_sn,
            'engine_sn': engine_sn,
            'trailer_hook': trailer_hook or False,
            'brand_new': brand_new or True,
            'account_prefix': account_prefix,
            'date_acquisition': acquisition_date,
            'value_original': original_value or 0,
            'fuel_card_openning_balance': fuel_card_openning_balance or 0,
            'fuel_card_budget': fuel_card_budget or 0,
            'highway_pass_openning_balance': highway_pass_openning_balance or 0,
            'highway_pass_budget': highway_pass_budget or 0,
            'active': active,
        }
        
        stock_lot = env['stock.lot'].create(lot_vals)
        
        # Migrate fleet logs to product asset logs
        _migrate_vehicle_logs(env, vehicle_id, stock_lot.id)
        
        # Migrate fleet contracts to product asset logs  
        _migrate_vehicle_contracts(env, vehicle_id, stock_lot.id)
        
        _logger.debug(f"Migrated vehicle: {name} -> stock.lot ID {stock_lot.id}")
        return 1
        
    except Exception as e:
        _logger.error(f"Error migrating vehicle {name} (ID: {vehicle_id}): {str(e)}")
        raise


def _migrate_vehicle_logs(env, vehicle_id, lot_id):
    """Migrate fleet.vehicle.log to product.asset.log"""
    
    cr = env.cr
    
    # Check if fleet_vehicle_log table exists
    cr.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'fleet_vehicle_log'
    """)
    
    if cr.fetchone()[0] == 0:
        _logger.debug(f"No fleet_vehicle_log table found, skipping log migration for vehicle {vehicle_id}")
        return
    
    # Check which columns exist in fleet_vehicle_log table
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'fleet_vehicle_log'
    """)
    available_columns = [col[0] for col in cr.fetchall()]
    _logger.debug(f"Available columns in fleet_vehicle_log: {available_columns}")
    
    if not available_columns:
        _logger.debug(f"No columns found in fleet_vehicle_log table")
        return
    
    # Build query with only existing columns
    base_columns = ['id', 'date', 'odometer', 'amount', 'notes', 'state', 'vehicle_id']
    optional_columns = ['date_end', 'cost_type', 'vendor_id', 'driver_id', 'product_id']
    
    # Only select columns that exist
    selected_columns = [col for col in base_columns if col in available_columns]
    selected_optional = [col for col in optional_columns if col in available_columns]
    all_columns = selected_columns + selected_optional
    
    if not all_columns:
        _logger.debug(f"No valid columns found for fleet_vehicle_log migration")
        return
    
    # Get logs data
    query = f"SELECT {', '.join(all_columns)} FROM fleet_vehicle_log WHERE vehicle_id = %s"
    _logger.debug(f"Executing query: {query} with vehicle_id: {vehicle_id}")
    cr.execute(query, (vehicle_id,))
    
    logs_data = cr.fetchall()
    migrated_logs = 0
    
    _logger.debug(f"Found {len(logs_data)} logs for vehicle {vehicle_id}")
    
    for log_data in logs_data:
        # Create dictionary from column names and data
        log_dict = dict(zip(all_columns, log_data))
        
        # Extract values with defaults for missing columns
        log_id = log_dict.get('id')
        date = log_dict.get('date')
        date_end = log_dict.get('date_end')
        odometer = log_dict.get('odometer', 0)
        amount = log_dict.get('amount', 0)
        notes = log_dict.get('notes')
        state = log_dict.get('state', 'done')
        product_id = log_dict.get('product_id')
        vendor_id = log_dict.get('vendor_id')
        driver_id = log_dict.get('driver_id')
        
        try:
            log_vals = {
                'asset_id': lot_id,
                'date': date,  # Use 'date' instead of 'date_start'
                'company_id': env['stock.lot'].browse(lot_id).company_id.id,  # Use same company as the asset
            }
            
            # Only add fields that have values
            if product_id:
                log_vals['product_id'] = product_id
            if vendor_id:
                log_vals['vendor_id'] = vendor_id  
            if driver_id:
                log_vals['operator_id'] = driver_id
            if date_end:
                log_vals['date_end'] = date_end
            if odometer:
                log_vals['odometer'] = odometer
            if amount:
                log_vals['amount'] = amount
            if notes:
                log_vals['notes'] = notes
            if state:
                log_vals['state'] = state
                
            _logger.debug(f"Creating product.asset.log with vals: {log_vals}")
            env['product.asset.log'].create(log_vals)
            migrated_logs += 1
            
        except Exception as e:
            _logger.error(f"Error migrating log {log_id}: {str(e)}")
            # Continue with other logs
    
    _logger.info(f"Migrated {migrated_logs} logs for vehicle {vehicle_id}")


def _migrate_vehicle_contracts(env, vehicle_id, lot_id):
    """Migrate fleet.vehicle.log.contract to product.asset.log"""
    
    cr = env.cr
    
    # Check if contract table exists
    cr.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'fleet_vehicle_log_contract'
    """)
    
    if cr.fetchone()[0] == 0:
        return  # No contracts table
    
    # Check which columns exist in fleet_vehicle_log_contract table
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'fleet_vehicle_log_contract'
    """)
    available_columns = [col[0] for col in cr.fetchall()]
    
    # Build query with only existing columns
    base_columns = ['id', 'vehicle_id']
    optional_columns = ['name', 'start_date', 'expiration_date', 'amount', 
                       'notes', 'state', 'vendor_id', 'product_id']
    
    # Only select columns that exist
    selected_columns = [col for col in base_columns if col in available_columns]
    selected_optional = [col for col in optional_columns if col in available_columns]
    all_columns = selected_columns + selected_optional
    
    # Get contracts data
    query = f"SELECT {', '.join(all_columns)} FROM fleet_vehicle_log_contract WHERE vehicle_id = %s"
    cr.execute(query, (vehicle_id,))
    
    contracts_data = cr.fetchall()
    migrated_contracts = 0
    
    for contract_data in contracts_data:
        # Create dictionary from column names and data
        contract_dict = dict(zip(all_columns, contract_data))
        
        # Extract values with defaults for missing columns
        contract_id = contract_dict.get('id')
        name = contract_dict.get('name', f'Contract {contract_id}')
        start_date = contract_dict.get('start_date')
        expiration_date = contract_dict.get('expiration_date')
        amount = contract_dict.get('amount', 0)
        notes = contract_dict.get('notes')
        state = contract_dict.get('state', 'done')
        vendor_id = contract_dict.get('vendor_id')
        product_id = contract_dict.get('product_id')
        
        try:
            contract_vals = {
                'asset_id': lot_id,
                'product_id': product_id,
                'vendor_id': vendor_id,
                'date_start': start_date,
                'date_end': expiration_date,
                'amount': amount,
                'notes': notes or name,
                'state': state,
            }
            
            env['product.asset.log'].create(contract_vals)
            migrated_contracts += 1
            
        except Exception as e:
            _logger.error(f"Error migrating contract {contract_id}: {str(e)}")
            # Continue with other contracts
    
    _logger.debug(f"Migrated {migrated_contracts} contracts for vehicle {vehicle_id}")


def _validate_migration_results(env):
    """Validate that migration was successful"""
    _logger.info("Validating migration results...")
    
    cr = env.cr
    
    # Count original fleet vehicles
    cr.execute("SELECT COUNT(*) FROM fleet_vehicle WHERE active IN (true, false)")
    original_vehicles = cr.fetchone()[0]
    
    # Count migrated stock lots  
    cr.execute("SELECT COUNT(*) FROM stock_lot WHERE asset_type = 'vehicle'")
    migrated_assets = cr.fetchone()[0]
    
    # Count fleet logs
    cr.execute("SELECT COUNT(*) FROM fleet_vehicle_log")
    original_logs = cr.fetchone()[0]
    
    # Count migrated logs
    cr.execute("""
        SELECT COUNT(*) FROM product_asset_log pal
        JOIN stock_lot sl ON pal.asset_id = sl.id
        WHERE sl.asset_type = 'vehicle'
    """)
    migrated_logs = cr.fetchone()[0]
    
    # Count product templates created
    cr.execute("""
        SELECT COUNT(*) FROM product_template 
        WHERE asset_type = 'vehicle'
    """)
    created_templates = cr.fetchone()[0]
    
    _logger.info("=== Migration Results ===")
    _logger.info(f"Original fleet vehicles: {original_vehicles}")
    _logger.info(f"Migrated asset lots: {migrated_assets}")
    _logger.info(f"Created product templates: {created_templates}")
    _logger.info(f"Original fleet logs: {original_logs}")
    _logger.info(f"Migrated asset logs: {migrated_logs}")
    
    if migrated_assets < original_vehicles:
        _logger.warning(f"Migration incomplete: {original_vehicles - migrated_assets} vehicles not migrated")
    else:
        _logger.info("All vehicles migrated successfully!")
    
    return {
        'original_vehicles': original_vehicles,
        'migrated_assets': migrated_assets,
        'created_templates': created_templates,
        'original_logs': original_logs,
        'migrated_logs': migrated_logs,
    }