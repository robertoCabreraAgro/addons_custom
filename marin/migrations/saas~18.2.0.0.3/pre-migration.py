import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Fix orphaned cron job references before module loading."""
    fix_orphaned_cron_references(cr)


def fix_orphaned_cron_references(cr):
    """Fix foreign key constraint violations for ir_cron -> ir_act_server."""
    
    _logger.info("Starting pre-migration to fix orphaned cron references")
    
    # First, eliminate cron jobs that reference problematic server actions
    # Note: Using DELETE instead of UPDATE because ir_actions_server_id cannot be NULL
    _logger.info("Eliminating cron jobs that reference problematic server actions...")
    cr.execute("""
        DELETE FROM ir_cron 
        WHERE ir_actions_server_id IN (
            SELECT ias.id 
            FROM ir_act_server ias
            LEFT JOIN ir_model_data imd ON (imd.res_id = ias.id AND imd.model = 'ir.actions.server')
            WHERE imd.name LIKE '%ir_cron_initialize_invoice_line_out_report%'
               OR imd.name LIKE '%invoice_line_out_report%'
               OR ias.name::text LIKE '%Initialize Invoice Line Out Report%'
               OR ias.name::text LIKE '%invoice_line_out_report%'
        )
    """)
    
    deleted_crons = cr.rowcount
    _logger.info("Deleted %s problematic cron jobs", deleted_crons)
    
    # Also eliminate any cron job with orphaned server action references
    _logger.info("Eliminating cron jobs with orphaned server action references...")
    cr.execute("""
        DELETE FROM ir_cron 
        WHERE ir_actions_server_id IS NOT NULL
          AND ir_actions_server_id NOT IN (SELECT id FROM ir_act_server)
    """)
    
    deleted_orphaned_crons = cr.rowcount
    _logger.info("Deleted %s cron jobs with orphaned references", deleted_orphaned_crons)
    
    # Now eliminate the problematic server actions
    _logger.info("Eliminating problematic server actions...")
    cr.execute("""
        DELETE FROM ir_act_server 
        WHERE id IN (
            SELECT ias.id 
            FROM ir_act_server ias
            LEFT JOIN ir_model_data imd ON (imd.res_id = ias.id AND imd.model = 'ir.actions.server')
            WHERE imd.name LIKE '%ir_cron_initialize_invoice_line_out_report%'
               OR imd.name LIKE '%invoice_line_out_report%'
               OR ias.name::text LIKE '%Initialize Invoice Line Out Report%'
               OR ias.name::text LIKE '%invoice_line_out_report%'
        )
    """)
    
    deleted_servers = cr.rowcount
    _logger.info("Deleted %s problematic server actions", deleted_servers)
    
    # Clean up orphaned ir_model_data entries
    _logger.info("Cleaning up orphaned ir_model_data entries...")
    cr.execute("""
        DELETE FROM ir_model_data 
        WHERE model = 'ir.actions.server' 
          AND res_id NOT IN (SELECT id FROM ir_act_server)
          AND (name LIKE '%invoice_line_out_report%' 
               OR name LIKE '%ir_cron_initialize_invoice_line_out_report%')
    """)
    
    deleted_model_data = cr.rowcount
    _logger.info("Deleted %s orphaned ir_model_data entries", deleted_model_data)
    
    _logger.info("Pre-migration completed successfully - eliminated %s cron jobs, %s server actions, and %s model data entries", 
                deleted_crons + deleted_orphaned_crons, deleted_servers, deleted_model_data)