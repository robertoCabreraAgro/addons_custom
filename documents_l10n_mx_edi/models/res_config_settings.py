from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_edi_esignature_ids = fields.Many2many(
        related="company_id.l10n_mx_edi_esignature_ids",
        string="MX E-signature",
        readonly=False,
    )
    l10n_mx_edi_folder = fields.Many2one(related="company_id.l10n_mx_edi_folder", readonly=False)
