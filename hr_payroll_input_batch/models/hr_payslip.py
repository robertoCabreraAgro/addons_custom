from odoo import Command, models
from odoo.tools import groupby


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def update_inputs_from_batch(self):
        """Update the extra inputs defined for the employees"""
        if not self:
            return False
        extras = self.env["hr.payslip.input.batch"].search(
            [("state", "=", "approved"), ("date", "=", self.mapped("payslip_run_id").date_start or self[0].date_from)]
        )
        for slip in self.filtered("contract_id"):
            slip_extras = extras.mapped("detail_ids").filtered(
                lambda e: e.employee_id == slip.employee_id and e.amount
            )
            slip.input_line_ids.filtered(lambda l: l.code in slip_extras.mapped("extra_id.input_id.code")).unlink()
            for extra, _records in groupby(slip_extras, lambda r: r.extra_id):
                slip.input_line_ids = [
                    Command.create(
                        {
                            "amount": sum(slip_extras.filtered(lambda e: e.extra_id == extra).mapped("amount")),
                            "code": extra.input_id.code,
                            "contract_id": slip.contract_id.id,
                            "input_type_id": extra.input_id.id,
                        },
                    )
                ]
            slip.compute_sheet()
        return True
