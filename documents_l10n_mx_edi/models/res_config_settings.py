from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_edi_esignature_ids = fields.Many2many(
        related="company_id.l10n_mx_edi_esignature_ids", string="MX E-signature", readonly=False
    )
    last_sat_fetch_date = fields.Datetime(
        "Last CFDI fetch date", related="company_id.last_sat_fetch_date", readonly=False
    )
    documents_l10n_mx_edi_folder_settings = fields.Boolean(
        related="company_id.documents_l10n_mx_edi_folder_settings", readonly=False
    )
    l10n_mx_edi_folder = fields.Many2one(related="company_id.l10n_mx_edi_folder", readonly=False)

    def sync_sat(self):
        self.company_id.download_cfdi_files()
        return True
