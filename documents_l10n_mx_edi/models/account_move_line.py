from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_mx_edi_is_ecc = fields.Boolean(help="Indicates that comes from a Fuel Account Statement complement")
