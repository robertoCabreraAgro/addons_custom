from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _get_existing_lines(self, line_ids, line, account_id, debit, credit):
        if line.slip_id.company_id.not_global_entry:
            return False
        return super()._get_existing_lines(line_ids, line, account_id, debit, credit)

    def _action_create_account_move(self):
        """Removes the payslip_run_id temporarily to generate an entry for each payslip."""
        if not self.contract_id.company_id.not_global_entry:
            return super()._action_create_account_move()

        for record in self:
            slip_run = record.payslip_run_id
            record.payslip_run_id = False
            super(HrPayslip, record)._action_create_account_move()
            record.payslip_run_id = slip_run
        return True
