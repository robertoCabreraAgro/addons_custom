from odoo import fields, models


class HrContractType(models.Model):
    _inherit = "hr.contract.type"

    l10n_mx_edi_code = fields.Char(
        "SAT Code",
        help="Define the SAT code for this record. This value will be used in the CFDI.",
    )
