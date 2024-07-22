from odoo import fields, models


class HrPayslipExtraPerception(models.Model):
    _name = "hr.payslip.extra.perception"
    _description = "Pay Slip extra perception"

    payslip_id = fields.Many2one(
        "hr.payslip",
        required=True,
        ondelete="cascade",
        help="Payslip related.",
    )
    node = fields.Selection(
        selection=[
            ("retirement", "JubilacionPensionRetiro"),
            ("separation", "SeparacionIndemnizacion"),
        ],
        help="Indicate what is "
        'the record purpose, if will be used to add in node "JubilacionPensionRetiro" or in "SeparacionIndemnizacion"',
    )
    amount_total = fields.Float(
        help='If will be used in the node "JubilacionPensionRetiro" and '
        'will be used to one perception with code "039", will be used to '
        'the attribute "TotalUnaExhibicion", if will be used to one '
        'perception with code "044", will be used to the attribute '
        '"TotalParcialidad". If will be used in the node '
        '"SeparacionIndemnizacion" will be used in attribute "TotalPagado"'
    )
    amount_daily = fields.Float(
        help='Used when will be added in node "JubilacionPensionRetiro", to be used in attribute "MontoDiario"'
    )
    accumulable_income = fields.Float(
        help="Used to both nodes, each record must be have the valor to each one.",
    )
    non_accumulable_income = fields.Float(
        help="Used to both nodes, each record must be have the valor to each one.",
    )
    service_years = fields.Integer(
        help='Used when will be added in node "SeparacionIndemnizacion", to be used in attribute "NumAñosServicio"',
    )
    last_salary = fields.Float(
        help='Used when will be added in node "SeparacionIndemnizacion", to '
        'be used in attribute "UltimoSueldoMensOrd"',
    )
