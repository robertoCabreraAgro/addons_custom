from odoo import fields, models


class ConsolidationCompanyPeriod(models.Model):
    _inherit = "consolidation.company_period"

    company_code = fields.Char(related="company_id.code")
