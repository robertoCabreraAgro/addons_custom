from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_mx_edi_fiscal_regime_ids = fields.Many2many(
        "l10n_mx_edi.fiscal.regime",
        compute="_compute_l10n_mx_edi_fiscal_regime_ids",
        string="Allowed Fiscal Regimes",
        help="Fiscal regimes allowed for CFDI emission on this journal.",
    )
    l10n_mx_edi_fiscal_regime_id = fields.Many2one(
        "l10n_mx_edi.fiscal.regime",
        string="Fiscal Regime",
        domain="[('id', 'in', l10n_mx_edi_fiscal_regime_ids)]",
        help="Default fiscal regime for this partner",
    )

    @api.depends("company_id.partner_id.l10n_mx_edi_fiscal_regime_ids")
    def _compute_l10n_mx_edi_fiscal_regime_ids(self):
        """Compute the allowed fiscal regimes based on the company's partner configuration."""
        for journal in self:
            journal.l10n_mx_edi_fiscal_regime_ids = (
                journal.company_id.partner_id.l10n_mx_edi_fiscal_regime_ids
            )

    @api.constrains("l10n_mx_edi_fiscal_regime_id")
    def _check_l10n_mx_edi_fiscal_regime_id(self):
        for journal in self:
            if (
                journal.l10n_mx_edi_fiscal_regime_id
                and journal.l10n_mx_edi_fiscal_regime_id
                not in journal.company_id.partner_id.l10n_mx_edi_fiscal_regime_ids
            ):
                raise ValidationError(
                    self.env._(
                        "The default emitter fiscal regime must be one of the allowed fiscal regimes for the company."
                    )
                )
