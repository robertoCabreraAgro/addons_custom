from datetime import datetime, timedelta

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    compute_root_category(env)
    populate_materialized_views(env)


def compute_root_category(env):
    """Compute the root category for all product categories."""
    env["product.category"].search([])._compute_root_category()


def populate_materialized_views(env):
    """Set crons that populate the materialized views to be executed 10 minutes after update"""
    crons = (
        env.ref("marin.ir_cron_update_invoice_line_in_report")
        | env.ref("marin.ir_cron_update_invoice_line_out_report")
        | env.ref("marin.ir_cron_update_pos_line_report")
        | env.ref("marin.ir_cron_update_stock_need_report")
    )
    crons.write(
        {
            "nextcall": datetime.now() + timedelta(minutes=10),
        }
    )
