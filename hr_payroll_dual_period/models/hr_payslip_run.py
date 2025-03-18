from odoo import fields, models


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    show_secondary_date_fields = fields.Boolean(
        related="company_id.show_secondary_date_fields"
    )
    secondary_date_from = fields.Date(
        help="If the payroll period is different to the dates that must be show in the PDF, please set here the real date "
        "from. If is empty, will be used the Date From.",
    )
    secondary_date_to = fields.Date(
        help="If the payroll period is different to the dates that must be show in the PDF, please set here the real date "
        "to. If is empty, will be used the Date To.",
    )
