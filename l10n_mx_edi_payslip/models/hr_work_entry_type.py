from odoo import fields, models


class HrWorkEntryType(models.Model):
    _inherit = "hr.work.entry.type"

    l10n_mx_edi_factor = fields.Float(
        "Factor",
        default=1,
        help="Indicates the factor to affect the salary rules related. Some companies affect an "
        "unjustified absence with 1.1, with this, the leave will be multiplied for this factor.",
    )
