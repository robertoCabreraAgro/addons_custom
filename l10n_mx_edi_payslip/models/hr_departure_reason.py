from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = "hr.departure.reason"

    l10n_mx_code = fields.Char(
        "Code",
        help="Set the Mexican code for this departure reason, will be used in the IDSE report.\n"
        "1: Contract End\n2: Voluntary separation\n3: Job Abandonment\n4: Death\n5: Closure\n6: Other",
    )
