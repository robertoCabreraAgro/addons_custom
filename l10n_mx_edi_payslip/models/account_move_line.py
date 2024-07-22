from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_mx_edi_payslip_line_ids = fields.Many2many(
        "hr.payslip.line",
        string="Payslip Line",
        readonly=True,
        copy=False,
        help="Payslip lines where the move line come from",
    )
    l10n_mx_edi_employer_registration_id = fields.Many2one(
        "l10n_mx_edi.employer.registration",
        "Employer Registration",
        groups="hr.group_hr_user",
        compute="_compute_l10n_mx_edi_employer_registration_id",
        store=True,
        help="Save the employer registration of the employee related with this journal item. "
        "(If this comes from a payroll).",
    )

    @api.depends("partner_id")
    def _compute_l10n_mx_edi_employer_registration_id(self):
        for record in self:
            if not record.l10n_mx_edi_payslip_line_ids:
                record.l10n_mx_edi_employer_registration_id = False
                continue
            employee = self.env["hr.employee"].search([("work_contact_id", "=", record.partner_id.id)], limit=1)
            record.l10n_mx_edi_employer_registration_id = (
                employee.l10n_mx_edi_employer_registration_id
                if (employee and employee.l10n_mx_edi_employer_registration_id)
                else False
            )
