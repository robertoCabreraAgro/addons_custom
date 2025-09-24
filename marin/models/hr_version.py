from datetime import time
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrVersion(models.Model):
    """Inherit HrVersion"""

    _inherit = "hr.version"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    structure_default_id = fields.Many2one(
        comodel_name="hr.payroll.structure",
        string="Structure",
        tracking=True,
    )

    # Override original method
    # @api.constrains('employee_id', 'contract_date_start', 'contract_date_end')
    # def _check_dates(self):
    # TODO in 19 this is the method that should be overriden

    def _l10n_mx_edi_year_days(self, date=False):
        """Given a date return the number of days in the dates year taking into account leap ones
        :return: a int 365 or 366 for a date in a leap year.
        """
        year = float(date.strftime("%Y")) if date else float(time.strftime("%Y"))
        return 366 if (not year % 4 and year % 100 or not year % 400) else 365

    # Override custom method
    def get_seniority(self, date_from=False, date_to=False, flag="r"):
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
        date_from = date_from or self.contract_date_start
        date_to = date_to or fields.Date.today()
        relative_seniority = relativedelta(date_to, date_from)
        if flag == "r":
            return {
                "years": relative_seniority.years,
                "months": relative_seniority.months,
                "days": relative_seniority.days,
            }
        return {
            "years": relative_seniority.years,
            "months": (relative_seniority.months + relative_seniority.years * 12),
            "days": (date_to - date_from).days + 1,
        }

    def _get_vacation_days(self, date_from=False, date_to=False):
        date_from = date_from or self.contract_date_start
        date_to = date_to or fields.Date.today()
        seniority = self.get_seniority(date_from, date_to)
        seniority = seniority.get("years", 0)
        table = [
            (0, 1, 0),
            (1, 2, 12),
            (2, 3, 14),
            (3, 4, 18),
            (4, 5, 18),
            (5, 6, 20),
            (6, 11, 22),
            (11, 16, 24),
            (16, 21, 26),
            (21, 26, 28),
            (26, 31, 30),
            (31, 99, 32),
        ]
        vacation_days = 0
        for value in table:
            if value[1] > seniority >= value[0]:
                vacation_days = value[2]
                break
        return vacation_days

    # Override original method
    def _get_integration_factor(self, date_from=False, date_to=False):
        """get the factor used to get the static integrated salary
        overwrite to add new static perceptions.
        factor = 1 + static perceptions/365
        new_factor = factor + new_perception / 365
        """
        self.ensure_one()
        vacation_bonus = (self.l10n_mx_edi_vacation_bonus or 25) / 100
        holidays = self._get_vacation_days(date_from, date_to)
        holidays = holidays if holidays else 12 * vacation_bonus
        bonus = self.l10n_mx_edi_christmas_bonus or 15
        return round(1 + (holidays + bonus) / 365, 4)

    # Override original method
    def _get_static_sdi(self, wage=None, date_from=False, date_to=False):
        """Get the integrated salary for the static perceptions like:
        - Salary
        - holidays
        - Christmas bonus
        """
        self.ensure_one()
        return (
            (wage / 30) if wage else self.l10n_mx_edi_daily_wage
        ) * self._get_integration_factor(date_from, date_to)

    # Override original method
    def _get_integrated_salary(self, wage=None, date_from=False, date_to=False):
        self.ensure_one()
        sdi = self._get_static_sdi(wage, date_from, date_to)
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
