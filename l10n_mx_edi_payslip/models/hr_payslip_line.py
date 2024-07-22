from odoo import fields, models


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    journal_item_ids = fields.Many2many(
        "account.move.line",
        string="Journal Items",
        help="Journal items created by this payslip line when was validated.",
    )
    l10n_mx_edi_schedule_pay_id = fields.Many2one(
        related="contract_id.l10n_mx_edi_schedule_pay_id",
        store=True,
    )
