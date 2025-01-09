from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        res = super()._prepare_line_values(line, account_id, date, debit, credit)
        res["partner_id"] = res.get("partner_id", False) or line.employee_id.work_contact_id.id
        res["salary_rule_id"] = line.salary_rule_id.id
        return res
