from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_edi_minimum_wage = fields.Float(
        "Mexican minimum Wage",
        help="Indicates the current daily amount of the general minimum wage in Mexico",
    )
    l10n_mx_edi_uma = fields.Float(
        "Mexican UMA",
        help="Indicates the current UMA in Mexico",
    )
    l10n_mx_edi_umi = fields.Float(
        "Mexican UMI",
        help="Indicates the current UMI in Mexico",
    )
    l10n_mx_edi_not_global_entry = fields.Boolean(
        "Not global entry?",
        help="If True, not will be generated a journal entry by month. (Odoo Process), will be "
        "generated a entry by each payslip.",
    )
    l10n_mx_edi_dynamic_name = fields.Boolean(
        "Dynamic concepts?",
        help="If true, the payslip concepts based on inputs could be dynamic.\nFor example: "
        "If employee will to receive 100 MXN by concept of sale commissions, the commission input could have the "
        'name "Commissions for SO12345", and that name will be set on the CFDI.',
    )
    l10n_mx_edi_vacation_bonus = fields.Selection(
        selection=[
            ("on_holidays", "On Holidays"),
            ("on_anniversary", "On Anniversary"),
            ("on_christmas_bonus", "On Christmas"),
        ],
        string="Vacation Bonus",
        default="on_holidays",
        help="Indicate when the company will to pay the vacation bonus.",
    )
    l10n_mx_edi_percentage_saving_fund = fields.Float(
        "Percentage of saving fund",
        help="If the company have the option to saving fund, indicate the percentage.",
    )
    l10n_mx_edi_isr_annual_adjustment = fields.Boolean(
        "ISR Annual Adjustment?",
        help="If it is checked, the ISR calculation will not be adjusted in the last payroll of the month, it will "
        "be the same according to the corresponding table. You must make an annual ISR adjustment, since at "
        "the end of the year there may be differences between the effectively withheld ISR and the actual ISR.",
    )
    l10n_mx_edi_payslip_email_alias = fields.Char(
        "Payslips Email Alias",
        help="Set a custom email alias for payslip. Your employees will receive their payslip from this alias.",
    )
    l10n_mx_edi_payslip_email = fields.Char(
        "Payslip Email Alias",
        compute="_compute_l10n_mx_edi_payslip_email",
        help="Custom Email to send payslip receipts",
    )
    l10n_mx_edi_automatic_settlement = fields.Boolean(
        "Use Automatic Settlement?",
        help="If it is checked, the salary structure Nómina will be replace to Nómina + finiquito "
        "When the contract expires on the same day as the end date of the period",
    )
    l10n_mx_edi_days_daily_wage = fields.Float(
        "Days for Daily Wage",
        default=30.0,
        help="Number of days to consider in the daily wage for the employees",
    )
    l10n_mx_edi_tolerance_check_in = fields.Float(
        "Tolerance in check in",
        help="If will be used the attendance in Odoo, indicate here the tolerance for "
        "check in, this will to get the attendances out of time and will be considered in some salary rules.",
    )
    l10n_mx_edi_subsidy_imss = fields.Boolean(
        "Subsidy Social Security?",
        help="If this option is checked, the social security fee will be subsidy by the "
        "company to the employees who receive the minimum wage.",
    )
    l10n_mx_edi_prorate_isr = fields.Boolean(
        "Prorate ISR on worked days?",
        help="If True, will to prorate the ISR and subsidy based on worked days.",
    )
    l10n_mx_edi_company_feeding = fields.Boolean(
        "Company contribution for feeding?",
        help="If the company provides the 50% for feeding mark this option and "
        "the feeding will be 50% employee and 50% the company, else, only will be affected the deduction for the "
        "employee.",
    )
    l10n_mx_edi_not_limit_saving_fund = fields.Boolean(
        "Ignore the limit for saving fund?",
        help="The law indicates that the saving fund amount in the year not must "
        "to exceeds the equivalent amount to 1.3 times the UMA of the year, this to be exempt. If the company not "
        "consider this limit enable this option.",
    )
    l10n_mx_edi_salary_worked_days = fields.Boolean(
        "Salary based on period days?",
        help="If this option is enabled, the perception to salary will to consider "
        "the days on the payslip period, else, the days on the schedule pay.",
    )
    l10n_mx_edi_electronic_food_voucher = fields.Boolean(
        "Uses Electronic Food Voucher?",
        help="If this option is enabled, the deduction for electronic food voucher "
        "will be added to the ordinary payslips.",
    )
    l10n_mx_edi_use_leave_deduction = fields.Boolean(
        "Use unpaid leaves as deductions?",
        help="If this option is enabled, the salary rules for unpaid leaves will be created as deductions and will "
        "get its on concepts in the payslip and in the CFDI, if not, the leaves will be calculated as auxiliars and "
        "their amount will be reduced in Sueldos, Salarios Rayas y Jornales.",
    )
    l10n_mx_edi_subsidy_sick_leaves = fields.Boolean(
        "Subsidy sick leaves?",
        help="If it is checked, the first three days of the sick inability will be subsidy by the company. "
        "The amount for those days will be no deducted.",
    )
    l10n_mx_edi_accumulate_holidays = fields.Boolean(
        "Accumulate Holidays?",
        help="If it is checked, the holidays allocation feature will accrue days over the years for the benefit "
        "of the employees.",
    )
    l10n_mx_edi_isr_174_bonus = fields.Boolean(
        "Use LISR 174 on bonus?",
        help="If True, will be used the LISR 174 on bonus.",
    )

    def _compute_l10n_mx_edi_payslip_email(self):
        for record in self:
            payslip_alias = record.l10n_mx_edi_payslip_email_alias
            alias_domain = self.env["ir.config_parameter"].sudo().get_param("mail.catchall.domain")
            email = "%s@%s" % (payslip_alias, alias_domain) if payslip_alias and alias_domain else ""
            record.l10n_mx_edi_payslip_email = email

    def write(self, values):
        """Inherit to update alimony for employees"""
        if "l10n_mx_edi_uma" not in values and "l10n_mx_edi_minimum_wage" not in values:
            return super().write(values)
        uma = self.l10n_mx_edi_uma
        vsm = self.l10n_mx_edi_minimum_wage
        res = super().write(values)
        if uma and uma != self.l10n_mx_edi_uma:
            factor = (self.l10n_mx_edi_uma - uma) / uma
            for ali in self.env["hr.employee.alimony"].search([("increase_based_on", "=", "uma")]):
                ali.write(
                    {
                        "discount_amount": ali.discount_amount * (1 + factor),
                    }
                )
        if vsm and vsm != self.l10n_mx_edi_minimum_wage:
            factor = (self.l10n_mx_edi_minimum_wage - vsm) / vsm
            for ali in self.env["hr.employee.alimony"].search([("increase_based_on", "=", "vsm")]):
                ali.write(
                    {
                        "discount_amount": ali.discount_amount * (1 + factor),
                    }
                )
        return res
