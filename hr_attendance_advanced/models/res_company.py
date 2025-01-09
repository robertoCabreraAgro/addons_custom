from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    exclude_previous_work_time = fields.Boolean(
        "Exclude Previous Work time?",
        help="If this field is enabled, the hours worked before the start of the workday will be exclude as overtime.",
    )

    tolerance_check_in = fields.Float(
        "Tolerance in check in",
        help="Specifies the tolerance time (in minutes) allowed for late check-ins. "
        "If an employee checks in within this tolerance period, it will be considered on time. "
        "This tolerance is used when processing attendance records and may also impact salary calculations.",
    )
