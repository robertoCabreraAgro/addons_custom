from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_load_all_partners_by_company = fields.Boolean(
        related="pos_config_id.load_all_partners_by_company", readonly=False
    )

    sat_batch_size = fields.Integer(
        string="Tamaño de lote para validación SAT",
        default=50,
        config_parameter="l10n_mx_edi_marin.sat_batch_size",
    )

    sat_status_max_days = fields.Integer(
        string="Días hábiles para revisión SAT",
        default=60,
        config_parameter="l10n_mx_edi_marin.sat_status_max_days",
    )
