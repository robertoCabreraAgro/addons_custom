from odoo import fields, models


class HrPayrollStructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    l10n_mx_edi_type = fields.Selection(
        selection=[
            ("O", "Ordinary"),
            ("E", "Extraordinary"),
        ],
        string="Payroll type",
        help="Value to assign in the attribute 'TipoNomina' in the CFDI.",
    )
