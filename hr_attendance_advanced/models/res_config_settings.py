from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    exclude_previous_work_time = fields.Boolean(
        related="company_id.exclude_previous_work_time",
        readonly=False,
    )

    tolerance_check_in = fields.Float(
        readonly=False,
        related="company_id.tolerance_check_in",
    )
