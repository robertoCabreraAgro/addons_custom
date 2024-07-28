from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_round


class AccountMove(models.Model):
    _inherit = "account.move"

    x_check_tax = fields.Monetary(
        "Verification tax",
        copy=False,
    )
    x_check_total = fields.Monetary(
        "Verification total",
        copy=False,
    )
    x_tax_difference = fields.Monetary("Tax difference", compute="_compute_x_difference")
    x_total_difference = fields.Monetary("Total difference", compute="_compute_x_difference")

    @api.constrains("state", "l10n_mx_edi_document_ids")
    def _check_uuid_duplicated(self):
        for move in self:
            if move.l10n_mx_edi_cfdi_uuid:
                dupli = self.search(
                    [
                        ("id", "!=", move.id),
                        ("l10n_mx_edi_cfdi_uuid", "=", move.l10n_mx_edi_cfdi_uuid),
                        ("company_id", "=", move.company_id.id),
                    ]
                )
                if dupli:
                    msg = _("UUID duplicated %s for following invoices:\n", move.l10n_mx_edi_cfdi_uuid)
                    for rec in dupli:
                        msg += "-(%s) %s\n" % (rec.id, rec.name)
                        raise ValidationError(msg)


    @api.depends("amount_tax", "amount_total", "x_check_tax", "x_check_total")
    def _compute_x_difference(self):
        for move in self:
            move.x_tax_difference = 0.0
            move.x_total_difference = 0.0
            if move.x_check_tax:
                move.x_tax_difference = float_round(
                    move.x_check_tax - move.amount_tax, precision_rounding=move.currency_id.rounding
                )
            if move.x_check_total:
                move.x_total_difference = float_round(
                    move.x_check_total - move.amount_total, precision_rounding=move.currency_id.rounding
                )
