from odoo import fields, models


class L10nMxEdiSchedulePay(models.Model):
    _name = "l10n_mx_edi.schedule.pay"
    _description = "Allow register the ISR table, code and days to pay for each schedule pay type in the sat catalog."

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Value from the SAT catalog.",
    )
    isr_table = fields.Text(
        "ISR Table",
        help="Define the ISR table for the ordinary payslip in this schedule pay.",
    )
    subsidy_table = fields.Text(help="Define the subsidy table for the ordinary payslip in this schedule pay.")
    days_to_pay = fields.Float(
        required=True,
        digits=(10, 4),
        help="Set the days to be paid in each payslip.",
    )
