import logging

from odoo import fields, models

ERROR_TYPE = [
    (0, "Token invalido."),
    (1, "Aceptada"),
    (2, "En proceso"),
    (3, "Terminada"),
    (4, "Error"),
    (5, "Rechazada"),
    (6, "Vencida"),
]


_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_edi_esignature_ids = fields.Many2many(
        "l10n_mx_edi.esignature", string="MX E-signature"
    )
    l10n_mx_edi_folder = fields.Many2one(
        "documents.document",
        default=lambda self: self.env.ref(
            "documents_l10n_mx_edi.documents_l10n_mx_edi_folder",
            raise_if_not_found=False,
        ),
    )
