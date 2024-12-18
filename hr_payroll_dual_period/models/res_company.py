from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    show_secondary_date_fields = fields.Boolean(
        help="If checked, it will enable secondary fields for date from and date to in the slips and batches to "
        "allow manage a second period for payroll."
    )
