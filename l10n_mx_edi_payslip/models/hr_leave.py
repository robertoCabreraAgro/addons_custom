from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    l10n_mx_edi_payslip_no_enjoy_days = fields.Boolean(
        "Not Enjoy Days?",
        tracking=True,
        help="Is this time off being paid but not enjoyed?",
    )

    @api.depends("date_from", "date_to", "resource_calendar_id", "holiday_status_id.request_unit")
    def _compute_duration(self):
        result = super()._compute_duration()
        calendar_leaves = self.filtered(
            lambda h: h.holiday_status_id.l10n_mx_edi_payslip_use_calendar_days and h.date_from and h.date_to
        )
        for holiday in calendar_leaves:
            holiday.number_of_days = (holiday.date_to - holiday.date_from).days + 1
        return result
