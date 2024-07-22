from odoo import _, api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _l10n_mx_edi_cfdi_check_invoice_config(self):
        res = super()._l10n_mx_edi_cfdi_check_invoice_config()
        if self.partner_id.l10n_mx_in_blocklist == "blocked":
            res.append(_("This partner is in the block list."))
        return res
