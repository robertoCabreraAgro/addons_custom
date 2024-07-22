from odoo import fields, models


class L10nMxEdiEmployerRegistration(models.Model):
    _name = "l10n_mx_edi.employer.registration"
    _description = "Allow define all the employer registration from the company"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(help='Value to set in the "RegistroPatronal" attribute.')
    job_risk_id = fields.Many2one(
        "l10n_mx_edi.job.risk",
        "Job Risk",
        required=True,
        tracking=True,
        help="Used in the XML to express the key according to the Class in "
        "which the employers must register, according to the activities "
        "carried out by their workers, as provided in article 196 of the "
        "Regulation on Affiliation Classification of Companies, Collection "
        "and Inspection, or in accordance with the regulations Of the Social "
        "Security Institute of the worker.",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(related="company_id.partner_id")
    branch_id = fields.Many2one(
        "res.partner",
        help="If the company have multi-branches, assign the employer registration branch.",
    )
    guide = fields.Char(
        "Guide Number",
        help="Number assigned for the delegation to this record. This will be used in the IDSE report.",
    )
    minimum_wage = fields.Float(
        help="Indicates the current daily minimum wage amount in this employer registration.",
    )
