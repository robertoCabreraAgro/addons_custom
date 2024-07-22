from odoo import fields, models


class L10nMxEdiJobRisk(models.Model):
    _name = "l10n_mx_edi.job.risk"
    _description = "Used to define the percent of each job risk."
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True,
        tracking=True,
        help="Job risk provided by the SAT.",
    )
    code = fields.Char(
        required=True,
        tracking=True,
        help="Code assigned by the SAT for this job risk.",
    )
    percentage = fields.Float(
        required=True,
        tracking=True,
        digits=(2, 6),
        help="Percentage for this risk, is used in the payroll rules.",
    )
    branch_id = fields.Many2one(
        "res.partner",
        tracking=True,
        help="If the company have multi-branches, assign the job risk branch.",
    )
