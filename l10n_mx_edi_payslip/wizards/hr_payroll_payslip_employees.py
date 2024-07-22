from odoo import _, api, models


class HrPayslipEmployees(models.TransientModel):
    _inherit = "hr.payslip.employees"

    def compute_sheet(self):
        """Inherit method to assign payment date in payslip created"""
        res = super().compute_sheet()
        payslip_obj = self.env["hr.payslip"]
        active_id = self.env.context.get("active_id")
        payslips = payslip_obj.search([("payslip_run_id", "=", active_id)])
        [run_data] = (
            self.env["hr.payslip.run"]
            .browse(active_id)
            .read(["l10n_mx_edi_payment_date", "l10n_mx_edi_date_start", "l10n_mx_edi_date_end"])
            if active_id
            else []
        )
        payslips.write(
            {
                "l10n_mx_edi_payment_date": run_data.get("l10n_mx_edi_payment_date", False),
                "l10n_mx_edi_date_from": run_data.get("l10n_mx_edi_date_start", False),
                "l10n_mx_edi_date_to": run_data.get("l10n_mx_edi_date_end", False),
                "number": payslips[0].payslip_run_id.name if payslips else "",
            }
        )

        if self.env.company.l10n_mx_edi_automatic_settlement:
            struct_id = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_01")
            changed_slips = payslips.filtered(
                lambda slip, st=struct_id: slip.date_to == slip.contract_id.date_end and slip.struct_id == struct_id
            )
            settlement_struct_id = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
            changed_slips.write({"struct_id": settlement_struct_id.id})
            message = _(
                """The contract will expire at the end of the payslip period.
                The salary structure was replaced from %(struct)s to %(sett)s""",
                struct=struct_id.name,
                sett=settlement_struct_id.name,
            )
            for slip in changed_slips:
                slip.message_post(body=_(message))

        payslips.l10n_mx_edi_update_extras()
        return res

    @api.onchange("structure_id")
    def _onchange_structure(self):
        if self.structure_id:
            self.employee_ids = False
