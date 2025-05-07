from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_mx_edi_require_uuid = fields.Boolean(
        string="Require a CFDI UUID",
        help="If checked, vendor bills created with this journal must have a CFDI UUID",
        default=False,
    )
