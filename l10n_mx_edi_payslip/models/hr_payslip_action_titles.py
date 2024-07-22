from odoo import fields, models


class HrPayslipActionTitles(models.Model):
    _name = "hr.payslip.action.titles"
    _description = "Pay Slip action titles"

    payslip_id = fields.Many2one(
        "hr.payslip",
        required=True,
        ondelete="cascade",
        help="Payslip related.",
    )
    category_id = fields.Many2one(
        "hr.salary.rule.category",
        "Category",
        required=True,
        help="Indicate to which perception will be added this attributes in node XML",
    )
    market_value = fields.Float(
        required=True,
        help="When perception type is 045 this value must be assigned in the "
        'line. Will be used in node "AccionesOTitulos" to the attribute "ValorMercado"',
    )
    price_granted = fields.Float(
        required=True,
        help="When perception type is 045 this value must be assigned in the "
        'line. Will be used in node "AccionesOTitulos" to the attribute "PrecioAlOtorgarse"',
    )
