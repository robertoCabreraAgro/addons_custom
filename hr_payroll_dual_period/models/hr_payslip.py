import math

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    show_secondary_date_fields = fields.Boolean(
        related="company_id.show_secondary_date_fields"
    )
    secondary_date_from = fields.Date(
        help="If the payroll period is different to the dates that must be show in the PDF, please set here the real date "
        "from. If is empty, will be used the Date From.",
    )
    secondary_date_to = fields.Date(
        help="If the payroll period is different to the dates that must be show in the PDF, please set here the real date "
        "to. If is empty, will be used the Date To.",
    )

    def _get_period_name(self, cache):
        """Method override to use secondary dates to form period name when set, instead of Odoo base dates."""
        self.ensure_one()
        if not (self.secondary_date_from and self.secondary_date_to):
            return super()._get_period_name(cache)

        period_name = "%s - %s" % (
            self._format_date_cached(cache, self.secondary_date_from),
            self._format_date_cached(cache, self.secondary_date_to),
        )
        if self.is_wrong_duration:
            return period_name
        start_date = self.secondary_date_from
        end_date = self.secondary_date_to
        lang = self.employee_id.lang or self.env.user.lang
        week_start = self.env["res.lang"]._get_data(code=lang).week_start
        schedule = (
            self.contract_id.schedule_pay
            or self.contract_id.structure_type_id.default_schedule_pay
        )
        if schedule == "monthly":
            period_name = self._format_date_cached(cache, start_date, "MMMM Y")
        elif schedule == "quarterly":
            current_year_quarter = math.ceil(start_date.month / 3)
            period_name = self.env._(
                "Quarter %(quarter)s of %(year)s",
                quarter=current_year_quarter,
                year=start_date.year,
            )
        elif schedule == "semi-annually":
            year_half = start_date.replace(day=1, month=6)
            is_first_half = start_date < year_half
            period_name = (
                self.env._("1st semester of %s", start_date.year)
                if is_first_half
                else self.env._("2nd semester of %s", start_date.year)
            )
        elif schedule == "annually":
            period_name = start_date.year
        elif schedule == "weekly":
            wk_num = (
                start_date.strftime("%U")
                if week_start == "7"
                else start_date.strftime("%W")
            )
            period_name = self.env._(
                "Week %(week_number)s of %(year)s",
                week_number=wk_num,
                year=start_date.year,
            )
        elif schedule == "bi-weekly":
            week = int(
                start_date.strftime("%U")
                if week_start == "7"
                else start_date.strftime("%W")
            )
            first_week = week - 1 + week % 2
            period_name = self.env._(
                "Weeks %(week)s and %(week1)s of %(year)s",
                week=first_week,
                week1=first_week + 1,
                year=start_date.year,
            )
        elif schedule == "bi-monthly":
            start_date_string = self._format_date_cached(cache, start_date, "MMMM Y")
            end_date_string = self._format_date_cached(cache, end_date, "MMMM Y")
            period_name = self.env._(
                "%(start_date_string)s and %(end_date_string)s",
                start_date_string=start_date_string,
                end_date_string=end_date_string,
            )
        return period_name

    @api.depends("secondary_date_from", "secondary_date_to")
    def _compute_name(self):
        return super()._compute_name()
