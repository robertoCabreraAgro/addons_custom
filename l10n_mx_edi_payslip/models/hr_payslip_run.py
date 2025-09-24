import time
from odoo import api, fields, models


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    l10n_mx_edi_payment_date = fields.Date(
        "Payment Date",
        help="Save the payment date that will be added on CFDI.",
    )
    l10n_mx_edi_productivity_bonus = fields.Float(
        "Productivity Bonus",
        help="The amount to distribute to the employees in the payslips.",
    )

    def generate_payslips(self, version_ids=None, employee_ids=None):
        """Extend payslip generation to include Mexican EDI customizations"""
        res = super().generate_payslips(
            version_ids=version_ids, employee_ids=employee_ids
        )

        # Get payslips created in this run
        payslips = self.slip_ids

        # Apply payment date from payslip run
        if self.l10n_mx_edi_payment_date:
            payslips.write(
                {
                    "l10n_mx_edi_payment_date": self.l10n_mx_edi_payment_date,
                }
            )

        # Handle automatic settlement logic for Mexico
        if self.env.company.l10n_mx_edi_automatic_settlement:
            struct_id = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_01")
            changed_slips = payslips.filtered(
                lambda slip, st=struct_id: slip.date_to
                == slip.version_id.contract_date_end
                and slip.struct_id == struct_id
            )
            settlement_struct_id = self.env.ref(
                "l10n_mx_edi_payslip.payroll_structure_data_06"
            )
            changed_slips.write({"struct_id": settlement_struct_id.id})
            message = self.env._(
                """The contract will expire at the end of the payslip period.
                The salary structure was replaced from %(struct)s to %(sett)s""",
                struct=struct_id.name,
                sett=settlement_struct_id.name,
            )
            for slip in changed_slips:
                slip.message_post(body=self.env._(message))

        # Update Mexican EDI extras for all payslips
        payslips.l10n_mx_edi_update_extras()
        return res
