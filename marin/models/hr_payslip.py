from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslipInherit(models.Model):
    _name = "hr.payslip"
    _inherit = "hr.payslip"


    move_state = fields.Selection(
        related="move_id.state", string="Accounting Entry state", readonly=True, copy=False
    )


    @api.onchange("contract_id")
    def onchange_contract(self):
        self.struct_id = self.contract_id.structure_type_id.default_struct_id.id

    # Override original method
    def l10n_mx_edi_is_required(self):
        self.ensure_one()
        fiscal = self.struct_id.journal_id.x_treatment in ("fiscal_real", "fiscal_simulated")
        company = self.company_id or self.contract_id.company_id
        return company.country_id == self.env.ref("base.mx") and fiscal

    # Override original method
    def _l10n_mx_edi_create_payslip_values(self):
        self.ensure_one()
        if not self.contract_id:
            return {"error": self.env._("Employee has not a contract and is required")}
        seniority = self.contract_id.get_seniority(date_to=self.date_to)
        str_seniority = ""
        if seniority["years"] > 0:
            str_seniority = f"""P{seniority["years"]}Y{seniority["months"]}M{seniority["days"]}D"""
        elif seniority["years"] == 0 and seniority["months"] >= 1:
            str_seniority = f"""P{seniority["months"]}M{seniority["days"]}D"""
        else:
            str_seniority = f"""P{seniority["days"]}D"""
        perceptions_data = self.get_cfdi_perceptions_data()
        payroll = {
            "record": self,
            "company": self.company_id or self.contract_id.company_id,
            "employee": self.employee_id,
            "payslip_type": self.struct_id.type_id.l10n_mx_edi_type or "O",
            "number_of_days": int(
                sum(self.worked_days_line_ids.mapped("number_of_days"))
                or self.contract_id.l10n_mx_edi_schedule_pay_id.days_to_pay
            ),
            "date_start": self.contract_id.date_start,
            "seniority_emp": str_seniority,
            "is_settlement": bool(perceptions_data["total_compensation"]),
            "force_other_payments": self._l10n_mx_edi_force_other_payments(),
            "acc_number": self.employee_id.sudo().bank_account_id.acc_number,
        }
        payroll.update(self.employee_id.get_cfdi_employee_data(self.contract_id))
        payroll.update(perceptions_data)
        payroll.update(self.get_cfdi_deductions_data())
        payroll.update(self.get_cfdi_other_payments_data())
        payroll["inability_data"] = lambda i, p: p._get_inability_data(i)
        return payroll

    # def _create_account_move(self, values):
    #     if not values.get("partner_id") and not self.company_id.batch_payroll_move_lines:
    #         values["partner_id"] = self.employee_id.work_contact_id.id
    #     return super()._create_account_move(values)

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        res = super()._prepare_line_values(line, account_id, date, debit, credit)
        if not res.get("partner_id") and not self.company_id.batch_payroll_move_lines:
            res["partner_id"] = self.employee_id.work_contact_id.id
        return res

    def action_payslip_move_post(self):
        if not self.env.user.has_group("l10n_mx_edi_payslip.allow_validate_payslip"):
            raise UserError(_(
                "Only Managers who are allow to validate payslip can perform this operation"
            ))

        if self.filtered(lambda slip: slip.state != "done"):
            raise UserError(_(
                "Cannot post a payslip's account move that is not done."
            ))

        to_post = self.filtered(lambda slip: slip.state == "done")
        moves = to_post.mapped("move_id")
        moves._post(soft=False)
