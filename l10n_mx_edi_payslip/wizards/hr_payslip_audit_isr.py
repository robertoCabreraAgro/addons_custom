from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

ISR_TABLE_TEMPLATE = "l10n_mx_edi_payslip.isr_table_template"
SUBSIDY_TABLE_TEMPLATE = "l10n_mx_edi_payslip.subsidy_table_template"


class HrPayslipAuditIsr(models.TransientModel):
    _name = "hr.payslip.audit.isr"
    _description = "Show the amount and calculations for ISR"

    payslip_id = fields.Many2one("hr.payslip")
    isr_table = fields.Html(string="ISR Table")
    isr_table_name = fields.Char("Used ISR Table Name")
    subsidy_table = fields.Html(
        help="Used subsidy for employment table",
    )
    period_taxable_income = fields.Monetary(
        help="Base amount in this period to be taxable",
    )
    used_taxable_income = fields.Monetary(
        help="Base amount taxable used to get the ISR tax in the payslip",
    )
    lower_limit = fields.Monetary(
        help="It is the minimum value that exists when placing the income in the range "
        "of the ISR table for each period.",
    )
    higher_limit = fields.Monetary(
        help="It is the maximum value that exists when placing the income in the range of "
        "the ISR table for each period.",
    )
    excess_lower_limit = fields.Monetary(
        help="Excess value, which results from subtracting the minimum value of the "
        "range of the ISR table from the taxable base of the period.",
    )
    percentage = fields.Float(
        "Percentaje over the lower limit excess",
        help="Percentaje (%) that will be applied to the value exceeding the lower limit.",
    )
    marginal_tax = fields.Monetary(
        help="Resulting tax when applying the corresponding rate.",
    )
    fixed_tax_rate = fields.Monetary(
        help="Amount that must be added to the marginal tax, which is considered in the ISR table.",
    )
    monthly_isr = fields.Monetary(
        "ISR Monthly Tax to Withhold",
        help="The whole ISR amount to be withold in this month",
    )
    previous_isr = fields.Monetary(
        "Previuos ISR Withheld",
        help="Previuos Tax withheld Amount in this month.",
    )
    subsidy = fields.Monetary(
        "Employment Subsidy",
        help="Employment subsidy when the employee salary is low",
    )
    isr = fields.Monetary(
        "ISR Tax to Withhold",
        help="ISR tax amount to be withold in this payslip",
    )
    currency_id = fields.Many2one(
        related="payslip_id.contract_id.company_id.currency_id",
        help="Currency in company",
    )

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        payslip_id = self.env["hr.payslip"].browse(self._context.get("active_ids", []))
        # Get fields
        schedule_pay_id = self._get_schedule_pay(payslip_id)
        period_taxable_income, used_taxable_income = self._get_incomes(payslip_id)
        isr_values = self._get_isr(schedule_pay_id, used_taxable_income, payslip_id)
        # Set Values
        isr_table, subsidy_table = self._get_pretty_tables(schedule_pay_id)
        result.update(
            {
                "payslip_id": payslip_id.id,
                "isr_table_name": schedule_pay_id.name,
                "isr_table": isr_table,
                "subsidy_table": subsidy_table,
                "period_taxable_income": period_taxable_income,
                "used_taxable_income": used_taxable_income,
            },
            **isr_values
        )
        return result

    def _get_schedule_pay(self, payslip_id):
        """Compute the isr table, Use monthly table if it is the last payslip"""
        if not payslip_id.l10n_mx_edi_is_last_payslip():
            return payslip_id.contract_id.l10n_mx_edi_schedule_pay_id
        return self.env.ref("l10n_mx_edi_payslip.schedule_pay_monthly")

    def _get_pretty_tables(self, schedule_pay_id):
        isr_values = {"isr_lines": safe_eval(schedule_pay_id.isr_table)}
        isr_table = self.env["ir.qweb"]._render(ISR_TABLE_TEMPLATE, isr_values)
        subsidy_values = {"subsidy_lines": safe_eval(schedule_pay_id.subsidy_table)}
        subsidy_table = self.env["ir.qweb"]._render(SUBSIDY_TABLE_TEMPLATE, subsidy_values)
        return isr_table, subsidy_table

    def _get_incomes(self, payslip_id):
        taxed_rules = self.env.ref("l10n_mx_edi_payslip.hr_rule_total_taxed")
        taxed_rules += self.env.ref("l10n_mx_edi_payslip.hr_rule_total_taxed_bf")
        taxed_line = payslip_id.line_ids.filtered(lambda line: line.salary_rule_id.id in taxed_rules.ids)
        used_taxable_income = period_taxable_income = taxed_line.total
        # Get monthly taxable
        if not payslip_id.company_id.l10n_mx_edi_isr_annual_adjustment and payslip_id.l10n_mx_edi_is_last_payslip():
            taxed_categ = self.env.ref("l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_taxed")
            lines = payslip_id.employee_id.slip_ids.filtered(
                lambda slip: slip.state == "done"
                and slip.id != payslip_id.id
                and slip.date_from.month == payslip_id.date_from.month
                and slip.date_from.year == payslip_id.date_from.year
            ).mapped("line_ids")

            taxed = sum(lines.filtered(lambda li: li.category_id.id == taxed_categ.id).mapped("total"))
            leaves_amount = sum(
                lines.filtered(lambda li: li.code in ("D020", "IEG006", "IM006", "IRT006", "LPHC006", "FJSS")).mapped(
                    "total"
                )
            )
            used_taxable_income += taxed - leaves_amount
        return period_taxable_income, used_taxable_income

    def _get_subsidy_isr(self, schedule_pay_id, amount):
        table = safe_eval(schedule_pay_id.subsidy_table)
        for value in table:
            if value[0] <= amount <= value[1]:
                return value[2]
        return 0

    def _get_isr(self, schedule_pay_id, amount, payslip_id):
        """Get monthly ISR corresponding to the amount given."""
        table = safe_eval(schedule_pay_id.isr_table)
        lower_limit = (
            higher_limit
        ) = (
            excess_lower_limit
        ) = percentage = marginal_tax = fixed_tax_rate = monthly_isr = previous_isr = isr = 0  # noqa
        for value in table:
            if value[1] >= amount >= value[0]:
                lower_limit = value[0]
                percentage = value[3]
                fixed_tax_rate = value[2]
                higher_limit = value[1]
                excess_lower_limit = amount - lower_limit
                marginal_tax = excess_lower_limit * percentage
                isr = round(marginal_tax + fixed_tax_rate, 2)

        if payslip_id.l10n_mx_edi_is_last_payslip():
            rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_isr")
            lines = payslip_id.employee_id.slip_ids.filtered(
                lambda slip: slip.state == "done"
                and slip.id != payslip_id.id
                and slip.date_from.month == payslip_id.date_from.month
                and slip.date_from.year == payslip_id.date_from.year
            ).mapped("line_ids")
            previous_isr = sum(lines.filtered(lambda li: li.salary_rule_id == rule).mapped("total"))
            monthly_isr = isr
            isr -= previous_isr

        # Adding Subsidy for employment
        subsidy = self._get_subsidy_isr(schedule_pay_id, amount)
        isr = isr if not subsidy else isr - subsidy if isr >= subsidy else 0

        return {
            "lower_limit": lower_limit,
            "excess_lower_limit": excess_lower_limit,
            "higher_limit": higher_limit,
            "percentage": percentage * 100,
            "marginal_tax": marginal_tax,
            "fixed_tax_rate": fixed_tax_rate,
            "previous_isr": previous_isr,
            "monthly_isr": monthly_isr,
            "subsidy": subsidy,
            "isr": isr,
        }
