import calendar
from datetime import datetime, timedelta
from math import floor

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    l10n_mx_edi_daily_wage = fields.Float(
        "Daily Wage",
        tracking=True,
        store=True,
        compute="_compute_l10n_mx_edi_daily_wage",
        help="This is the daily wage used in the payroll mexican localization. Calculated by dividing the monthly "
        "wage by the number of days in the configuration in general options, 30.0 by default",
    )
    l10n_mx_edi_holidays = fields.Integer(
        string="Days of holidays",
        default=12,
        tracking=True,
        help="Initial number of days for holidays. The minimum is 12 days.",
    )
    l10n_mx_edi_vacation_bonus = fields.Integer(
        string="Vacation bonus (%)",
        default=25,
        tracking=True,
        help="Percentage of vacation bonus. The minimum is 25 %.",
    )
    l10n_mx_edi_christmas_bonus = fields.Integer(
        string="Christmas bonus (days)",
        default=15,
        tracking=True,
        help="Number of day for the Christmas bonus. The minimum is 15 days' pay",
    )
    l10n_mx_edi_sdi_variable = fields.Float(
        "Variable SDI",
        tracking=True,
        help="Used when the salary type is mixed or variable. This value is "
        "integrated by the sum of perceptions in the previous two months and "
        "divided by the number of days worked. Also, it affects the "
        "integrated salary value.",
    )
    l10n_mx_edi_sdi_total = fields.Float(
        compute="_compute_l10n_mx_edi_sdi_total",
        string="SDI",
        store=True,
        tracking=True,
        help="Get the sum of Variable SDI + Integrated Salary",
    )
    l10n_mx_edi_sbc = fields.Float(
        "SBC",
        tracking=True,
        store=True,
        compute="_compute_integrated_salary",
        help="Used in the CFDI to express the salary that is integrated with the payments made in cash by daily "
        "quota, gratuities, perceptions, room, premiums, commissions, benefits in kind and any other quantity or "
        "benefit that is delivered to the worker by his work, Pursuant to Article 84 of the Federal Labor Law.",
    )
    l10n_mx_edi_schedule_pay_id = fields.Many2one(
        "l10n_mx_edi.schedule.pay",
        string="Mexican Schedule Pay",
        default=lambda self: self.env.ref("l10n_mx_edi_payslip.schedule_pay_fortnightly", raise_if_not_found=False),
    )
    l10n_mx_edi_integrated_salary = fields.Float(
        "Integrated Salary",
        tracking=True,
        store=True,
        compute="_compute_integrated_salary",
        help="Used in the CFDI to express the salary "
        "that is integrated with the payments made in cash by daily quota, "
        "gratuities, perceptions, room, premiums, commissions, benefits in "
        "kind and any other quantity or benefit that is delivered to the "
        "worker by his work, Pursuant to Article 84 of the Federal Labor "
        "Law. (Used to calculate compensation).",
    )
    l10n_mx_edi_food_voucher = fields.Float(
        "Food Voucher Amount",
        tracking=True,
        help="Amount to be paid in food voucher each payment period.",
    )
    l10n_mx_edi_food_voucher_onerous = fields.Float(
        "Food Voucher Amount Onerous",
        tracking=True,
        help="Amount to be paid in food voucher onerous each payment period. If set, the food voucher amount "
        "not will be considered in the ISN. The common value is 1.00",
    )
    l10n_mx_edi_punctuality_bonus = fields.Float(
        "Punctuality bonus",
        tracking=True,
        help="If the company offers punctuality bonus, indicate the bonus amount by payment period.",
    )
    l10n_mx_edi_punctuality_bonus_type = fields.Selection(
        selection=[
            ("percentage", "Percentage"),
            ("fixed", "Fixed"),
        ],
        string="Punctuality Bonus Type",
        tracking=True,
        default="fixed",
        help="Defines how the bonus will be calculated.\nFixed: The bonus will be always the amount set\n"
        "Percentage: The bonus will be the employee salary percentage set, the recommended value is 10\n"
        "Empty: If any is selected the type will be considered as fixed",
    )
    l10n_mx_edi_attendance_bonus = fields.Float(
        "Attendance bonus",
        tracking=True,
        help="If the company offers attendance bonus, indicate the bonus amount by payment period.",
    )
    l10n_mx_edi_attendance_bonus_type = fields.Selection(
        selection=[
            ("percentage", "Percentage"),
            ("fixed", "Fixed"),
        ],
        string="Attendance Bonus Type",
        tracking=True,
        default="fixed",
        help="Defines how the bonus will be calculated.\nFixed: The bonus will be always the amount set\n"
        "Percentage: The bonus will be the employee salary percentage set, the recommended value is 10\n"
        "Empty: If any is selected the type will be considered as fixed",
    )
    l10n_mx_edi_salary_type = fields.Selection(
        selection=[
            ("0", "Fixed"),
            ("1", "Variable"),
            ("2", "Mixed"),
        ],
        string="Salary type",
        tracking=True,
        default="0",
        help="The action that updates automatically the SDI variable each bimester could discard "
        "contracts based on this field.",
    )
    l10n_mx_edi_working_type = fields.Selection(
        selection=[
            ("0", "Normal"),
            ("1", "1 day"),
            ("2", "2 days"),
            ("3", "3 days"),
            ("4", "4 days"),
            ("5", "5 days"),
            ("6", "Reduced"),
        ],
        string="Working Type",
        help="Indicate the working type, based on the IDSE report.",
    )
    l10n_mx_edi_feeding = fields.Float(
        "Feeding",
        help="Indicates the amount for each day, the total in the payslip will be this amount * the "
        "number of days that was used the service.",
    )
    l10n_mx_edi_feeding_type = fields.Selection(
        selection=[
            ("percentage", "Percentage"),
            ("fixed", "Fixed"),
        ],
        string="Feeding Type",
        tracking=True,
        default="fixed",
        help="Defines how the feeding will be calculated.\nFixed: The feeding will be always the amount set.\n"
        "Percentage: The feeding will be the percentage assigned * UMA amount.\n"
        "Empty: If any is selected the type will be considered as fixed.",
    )
    l10n_mx_edi_housing = fields.Float(
        "Housing",
        help="Help for rent or housing which will be excluded of the SBC, this number indicates the amount "
        "for each day, the total in the payslip will be this amount * the number of days that was "
        "used the service.",
    )
    l10n_mx_edi_housing_type = fields.Selection(
        selection=[
            ("percentage", "Percentage"),
            ("fixed", "Fixed"),
        ],
        string="Housing Type",
        tracking=True,
        default="fixed",
        help="Defines how the housing will be calculated.\n"
        "Fixed: The housing will be always the amount set.\n"
        "Percentage: The feeding will be the percentage assigned * UMA value * days.\n"
        "Empty: If any is selected the rule will be not calculated.",
    )
    l10n_mx_edi_chrismas_bonus_amortization = fields.Boolean(
        "Christmas Bonus Amortization",
        help="If check, the salary rule Provisión Anual will be calculated. "
        "The ISR for Christmas bonus will be pay in each payslip to amortize it.",
    )
    l10n_mx_edi_day_off = fields.Selection(
        selection=[
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        string="Day Off",
        help="Day off to Mexican payroll, the salary rule Septimo dia will use this "
        "day to be calculated, if is not set, the rule will consider Saturdays and Sundays as days off.",
    )
    l10n_mx_edi_electric_ho = fields.Float(
        "Electric for Home Office",
        tracking=True,
        help="If the company offers electric bonus for home office employees, indicate the bonus amount.",
    )
    l10n_mx_edi_internet_ho = fields.Float(
        "Internet for Home Office",
        tracking=True,
        help="If the company offers internet bonus for home office employees, indicate the bonus amount.",
    )
    l10n_mx_edi_allow_overtimes = fields.Boolean(
        "Allow overtimes?",
        tracking=True,
        help="If True, the overtimes for the employee will be generated when call the button to generate it.",
    )
    l10n_mx_edi_special_isr = fields.Float(
        "Special ISR deduction",
        tracking=True,
        help="If this set, the ISR percentage for this employee will always the value set. Normally a 35% is used. "
        "This option generally is used for partners, shareholders or for employees whose monthly income is very high.",
    )

    @api.depends("wage", "company_id.l10n_mx_edi_days_daily_wage")
    def _compute_l10n_mx_edi_daily_wage(self):
        for record in self.filtered(lambda c: c.country_code == "MX"):
            record.l10n_mx_edi_daily_wage = record.wage / (record.company_id.l10n_mx_edi_days_daily_wage or 30.0)

    @api.depends("l10n_mx_edi_integrated_salary", "l10n_mx_edi_sdi_variable")
    def _compute_l10n_mx_edi_sdi_total(self):
        for record in self.filtered(lambda c: c.country_code == "MX"):
            record.l10n_mx_edi_sdi_total = record.l10n_mx_edi_integrated_salary + record.l10n_mx_edi_sdi_variable

    @api.depends(
        "l10n_mx_edi_vacation_bonus",
        "l10n_mx_edi_christmas_bonus",
        "l10n_mx_edi_holidays",
        "wage",
        "date_start",
        "employee_id",
        "l10n_mx_edi_sdi_variable",
    )
    def _compute_integrated_salary(self):
        """Compute Daily Salary Integrated according to Mexican laws"""
        for record in self.filtered(lambda c: c.country_code == "MX"):
            sdi, sbc = record._get_integrated_salary()
            record.l10n_mx_edi_integrated_salary = sdi
            record.l10n_mx_edi_sbc = sbc

    def _get_integrated_salary(self, wage=None):
        self.ensure_one()
        sdi = self._get_static_sdi(wage)
        # the integrated salary cannot be less than 1 minimum wages
        minimum_wage = (
            self.employee_id.l10n_mx_edi_employer_registration_id.minimum_wage
            or self.company_id.l10n_mx_edi_minimum_wage
        )
        sdi = minimum_wage if sdi < minimum_wage else sdi
        l10n_mx_edi_integrated_salary = round(sdi, 2)
        # the integrated salary cannot be more than 25 UMAs
        max_sdi = self.company_id.l10n_mx_edi_uma * 25
        sdi = sdi + self.l10n_mx_edi_sdi_variable
        sdi = sdi if sdi < max_sdi else max_sdi
        return l10n_mx_edi_integrated_salary, round(sdi, 2)

    def compute_integrated_salary_variable(self):
        """Compute Daily Salary Integrated Variable according to Mexican laws"""
        payslips = self.env["hr.payslip"]
        date_mx = fields.datetime.now()
        date_from = (date_mx - timedelta(days=30 * (2 if date_mx.month % 2 else 3))).replace(day=1)
        date_to = date_mx - timedelta(days=30 * (1 if date_mx.month % 2 else 2))
        date_to = date_to.replace(day=calendar.monthrange(date_to.year, date_to.month)[1])
        for record in self:
            payslips = payslips.search(
                [
                    ("employee_id", "=", record.employee_id.id),
                    ("state", "=", "done"),
                    ("date_from", ">=", date_from),
                    ("date_to", "<=", date_to),
                ]
            )
            worked = sum(
                payslips.filtered(lambda p: p.struct_id.type_id.l10n_mx_edi_type == "O")
                .mapped("worked_days_line_ids")
                .filtered(lambda work: work.code == "WORK100")
                .mapped("number_of_days")
            )
            inputs = sum(
                payslips.mapped("line_ids").filtered("salary_rule_id.l10n_mx_edi_sdi_variable").mapped("total")
            )
            record.l10n_mx_edi_sdi_variable = (inputs / worked) if worked else 0

    def _get_static_sdi(self, wage=None):
        """Get the integrated salary for the static perceptions like:
        - Salary
        - holidays
        - Christmas bonus
        """
        self.ensure_one()
        return ((wage / 30) if wage else self.l10n_mx_edi_daily_wage) * self._get_integration_factor()

    def _get_integration_factor(self):
        """get the factor used to get the static integrated salary
        overwrite to add new static perceptions.
        factor = 1 + static perceptions/365
        new_factor = factor + new_perception / 365
        """
        self.ensure_one()
        vacation_bonus = (self.l10n_mx_edi_vacation_bonus or 25) / 100
        holidays = self.l10n_mx_edi_holidays * vacation_bonus
        bonus = self.l10n_mx_edi_christmas_bonus or 15
        return round(1 + (holidays + bonus) / 365, 4)

    def action_update_current_holidays(self):
        """Assign number of days according with the seniority and holidays"""
        # TODO - Moverlo a la metodología de listado de server action por contrato @nhomar
        for record in self:
            record.l10n_mx_edi_holidays = record._l10n_mx_get_holidays(record.get_seniority()["years"])

    @api.model
    def _l10n_mx_get_holidays(self, seniority):
        """Get how many holidays an employee has based on a given seniority.
        This method will be used by the assignation method and by the allocation cron."""
        holidays = 12
        if seniority < 5:
            return holidays + (2 * seniority)
        return holidays + 8 + 2 * floor(seniority / 5)

    def l10n_mx_allocate_annual_holidays(self, filter_by_anniversary=True):
        """In mexico each year, when the employee celebrates years on the company, the employee earn holidays,
        this method creates the leave allocation."""
        holiday = self.env.ref("l10n_mx_edi_payslip.mexican_holiday")
        mexico_tz = self.env["l10n_mx_edi.certificate"]._get_timezone()
        date_mx = datetime.now(mexico_tz)
        contracts = (
            self.filtered(
                lambda contract: contract.employee_id.private_country_id.code == "MX"
                and contract.date_start.day == date_mx.day
                and contract.date_start.month == date_mx.month
                and contract.date_start.year < date_mx.year
            )
            if filter_by_anniversary
            else self
        )

        for contract in contracts:
            # Create and confirm the new allocation
            allocation = self.env["hr.leave.allocation"].create(
                {
                    "name": f"{holiday.name} MX {date_mx.year}",
                    "holiday_status_id": holiday.id,
                    "number_of_days": contract._l10n_mx_get_holidays(contract.get_seniority()["years"] - 1),
                    "holiday_type": "employee",
                    "allocation_type": "regular",
                    "employee_id": contract.employee_id.id,
                    "state": "confirm",
                    "date_from": date_mx,
                    "date_to": False
                    if (contract.company_id.l10n_mx_edi_accumulate_holidays)
                    else (date_mx + relativedelta(years=1) - timedelta(days=1)),
                }
            )
            allocation.sudo().action_validate()
            contract.action_update_current_holidays()

    def get_seniority(self, date_from=False, date_to=False, method="r"):
        """Return seniority between contract's date_start and date_to or today

        :param date_from: start date (default contract.date_start)
        :type date_from: str
        :param date_to: end date (default today)
        :type date_to: str
        :param method: {'r', 'a'} kind of values returned
        :type method: str
        :return: a dict with the values years, months, days.
            These values can be relative or absolute.
        :rtype: dict
        """
        self.ensure_one()
        datetime_start = date_from or self.date_start
        date = date_to or fields.Date.today()
        relative_seniority = relativedelta(date, datetime_start)
        if method == "r":
            return {
                "years": relative_seniority.years,
                "months": relative_seniority.months,
                "days": relative_seniority.days,
            }
        return {
            "years": relative_seniority.years,
            "months": (relative_seniority.months + relative_seniority.years * 12),
            "days": (date - datetime_start).days + 1,
        }

    def _get_days_in_current_period(self, date_to=False, start_year=False):
        """Get days at current period to compute payments' proportional part

        :param date_to: date to get the days
        :type date_to: str
        :param start_year: period start at 1 Jan
        :type start_year: boolean
        :return: number of days of the contract in current period
        :rtype: int
        """
        date = date_to or fields.Date.today()
        contract_date = self.date_start
        if start_year:
            date_start = fields.date(date.year, 1, 1)
            if (contract_date - date_start).days > 0:
                date_start = contract_date
            return (date - date_start).days + 1
        date_start = fields.date(contract_date.year, contract_date.month, contract_date.day)
        if (date - date_start).days < 0:
            date_start = fields.date(date.year - 1, contract_date.month, contract_date.day)
        return (date - date_start).days + 1

    def _get_worked_leaves(self, date_from, date_to, domain=None):
        self.ensure_one()
        if not self.resource_calendar_id:
            return False
        work_hours = self._get_work_hours(date_from, date_to, domain=domain)
        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        return work_hours_ordered

    def write(self, vals):
        """If resource calendar is updated, the work entries must be regenerated."""
        result = super().write(vals)
        if vals.get("resource_calendar_id"):
            self._regenerate_work_entries_by_calendar()
        return result

    def _regenerate_work_entries_by_calendar(self):
        wizard = self.env["hr.work.entry.regeneration.wizard"]
        for contract in self.filtered(lambda c: c.employee_id and c.state == "open"):
            last_payslip = self.env["hr.payslip"].search(
                [("employee_id", "=", contract.employee_id.id), ("state", "=", "open")], order="date_from"
            )
            domain = [("employee_id", "=", contract.employee_id.id), ("state", "=", "draft")]
            if last_payslip:
                domain.append(("date_stop", ">=", last_payslip.date_to))
            work_entry = self.env["hr.work.entry"].search(domain, order="date_start")
            if not work_entry:
                continue
            wizard.create(
                {
                    "employee_ids": [Command.set(contract.employee_id.ids)],
                    "date_from": work_entry[0].date_start,
                    "date_to": work_entry[-1].date_stop,
                }
            ).regenerate_work_entries()
