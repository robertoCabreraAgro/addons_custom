from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    set_syngenta_code(cr)


def set_syngenta_code(cr):
    """Set syngenta code to all companies."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search([])
    if companies:
        companies.write({"syngenta_customer_code": "10283128"})
