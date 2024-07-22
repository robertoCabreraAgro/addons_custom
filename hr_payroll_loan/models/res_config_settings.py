from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    loan_generate_breakdown = fields.Boolean(
        related="company_id.loan_generate_breakdown",
        readonly=False,
    )
