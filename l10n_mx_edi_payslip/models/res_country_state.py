from odoo import fields, models


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    l10n_mx_payslip_isn = fields.Float(
        "State ISN Percentage",
        help="Indicates the percentage the payroll will use with employees "
        "who work on this state to calculate ISN Tax",
    )
