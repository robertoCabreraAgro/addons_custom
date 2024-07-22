from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    set_marin_vat_tax_parameter(cr)


def set_marin_vat_tax_parameter(cr):
    """Set the parameter for mapping IVA taxes."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.config_parameter"].sudo().set_param("marin.tax_iva", "VAT")
