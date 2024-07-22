from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_edi_minimum_wage = fields.Float(
        related="company_id.l10n_mx_edi_minimum_wage",
        readonly=False,
    )
    l10n_mx_edi_uma = fields.Float(
        related="company_id.l10n_mx_edi_uma",
        readonly=False,
    )
    l10n_mx_edi_umi = fields.Float(
        related="company_id.l10n_mx_edi_umi",
        readonly=False,
    )
    l10n_mx_edi_not_global_entry = fields.Boolean(
        related="company_id.l10n_mx_edi_not_global_entry",
        readonly=False,
    )
    l10n_mx_edi_dynamic_name = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_dynamic_name",
    )
    l10n_mx_edi_vacation_bonus = fields.Selection(
        readonly=False,
        related="company_id.l10n_mx_edi_vacation_bonus",
    )
    l10n_mx_edi_percentage_saving_fund = fields.Float(
        readonly=False,
        related="company_id.l10n_mx_edi_percentage_saving_fund",
    )
    l10n_mx_edi_isr_annual_adjustment = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_isr_annual_adjustment",
    )
    l10n_mx_edi_payslip_email_alias = fields.Char(
        readonly=False,
        related="company_id.l10n_mx_edi_payslip_email_alias",
    )
    l10n_mx_edi_automatic_settlement = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_automatic_settlement",
    )
    l10n_mx_edi_days_daily_wage = fields.Float(
        readonly=False,
        related="company_id.l10n_mx_edi_days_daily_wage",
    )
    l10n_mx_edi_tolerance_check_in = fields.Float(
        readonly=False,
        related="company_id.l10n_mx_edi_tolerance_check_in",
    )
    l10n_mx_edi_subsidy_imss = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_subsidy_imss",
    )
    l10n_mx_edi_prorate_isr = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_prorate_isr",
    )
    l10n_mx_edi_company_feeding = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_company_feeding",
    )
    l10n_mx_edi_not_limit_saving_fund = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_not_limit_saving_fund",
    )
    l10n_mx_edi_salary_worked_days = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_salary_worked_days",
    )
    l10n_mx_edi_electronic_food_voucher = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_electronic_food_voucher",
    )
    l10n_mx_edi_use_leave_deduction = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_use_leave_deduction",
    )
    l10n_mx_edi_subsidy_sick_leaves = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_subsidy_sick_leaves",
    )
    l10n_mx_edi_accumulate_holidays = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_accumulate_holidays",
    )
    l10n_mx_edi_isr_174_bonus = fields.Boolean(
        readonly=False,
        related="company_id.l10n_mx_edi_isr_174_bonus",
    )
