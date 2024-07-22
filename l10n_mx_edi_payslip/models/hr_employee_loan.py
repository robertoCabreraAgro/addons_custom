from odoo import api, fields, models


class HrEmployeeLoan(models.Model):
    _inherit = "hr.employee.loan"

    number_fonacot = fields.Char(
        tracking=True,
        help="If comes from Fonacot, indicate the number.",
    )
    infonavit_type = fields.Selection(
        selection=[
            ("percentage", "Percentage"),
            ("vsm", "Number of minimum wages"),
            ("fixed_amount", "Fixed amount"),
        ],
        tracking=True,
        string="Discount Type",
        help="INFONAVIT discount type that is calculated in the employee's payslip.",
    )

    @api.onchange("input_type_id")
    def onchange_input_type_id(self):
        for record in self:
            record.number_fonacot = False
            record.infonavit_type = False
