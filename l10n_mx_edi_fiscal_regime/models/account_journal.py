from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    default_emitter_fiscal_regime = fields.Many2one(
        "l10n_mx_edi.fiscal.regime",
        string="Default Emitter Fiscal Regime",
        domain="[('id', 'in', company_id.partner_id.allowed_fiscal_regimes.ids)]",
        help="Fiscal regime used as default for CFDI emission on this journal",
    )

    @api.constrains("default_emitter_fiscal_regime")
    def _check_default_emitter_fiscal_regime(self):
        for journal in self:
            if (
                journal.default_emitter_fiscal_regime
                and journal.default_emitter_fiscal_regime
                not in journal.company_id.partner_id.allowed_fiscal_regimes
            ):
                raise ValidationError(
                    self.env._(
                        "The default emitter fiscal regime must be one of the allowed fiscal regimes for the company."
                    )
                )

