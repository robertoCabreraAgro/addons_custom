from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    not_global_entry = fields.Boolean(
        "Not global entry?",
        help="If checked, a journal entry will be generated for each payroll in the batch "
        "instead of a monthly journal entry, as done in Odoo's native process.",
    )
