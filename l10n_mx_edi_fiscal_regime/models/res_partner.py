from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    """Inherit ResPartner"""

    _inherit = "res.partner"

    l10n_mx_edi_fiscal_regime_ids = fields.Many2many(
        "l10n_mx_edi.fiscal.regime",
        "partner_l10n_mx_edi_fiscal_regime_rel",
        "partner_id",
        "fiscal_regime_id",
        string="Allowed Fiscal Regimes",
        help="Fiscal regimes that this partner can use for invoicing",
    )
    l10n_mx_edi_fiscal_regime_id = fields.Many2one(
        "l10n_mx_edi.fiscal.regime",
        string="Fiscal Regime",
        domain="[('id', 'in', l10n_mx_edi_fiscal_regime_ids)]",
        help="Default fiscal regime for this partner",
    )

    # Computed field for backward compatibility
    l10n_mx_edi_fiscal_regime = fields.Char(
        string="Fiscal Regime",
        compute="_compute_l10n_mx_edi_fiscal_regime",
        readonly=False,
        store=True,
        help="Fiscal Regime is required for all partners (used in CFDI)",
    )

    @api.depends("country_code", "l10n_mx_edi_fiscal_regime_id")
    def _compute_l10n_mx_edi_fiscal_regime(self):
        """Re-compute fiscal regime code for backward compatibility."""
        res = super()._compute_l10n_mx_edi_fiscal_regime()
        for partner in self:
            if partner.country_code == "MX" and partner.l10n_mx_edi_fiscal_regime_id:
                partner.l10n_mx_edi_fiscal_regime = (
                    partner.l10n_mx_edi_fiscal_regime_id.code
                )
        return res

    @api.constrains("l10n_mx_edi_fiscal_regime_id", "l10n_mx_edi_fiscal_regime_ids")
    def _check_l10n_mx_edi_fiscal_regime_id(self):
        """Validate that default fiscal regime is within allowed fiscal regimes."""
        for partner in self:
            if (
                partner.l10n_mx_edi_fiscal_regime_id
                and partner.l10n_mx_edi_fiscal_regime_ids
            ):
                if (
                    partner.l10n_mx_edi_fiscal_regime_id
                    not in partner.l10n_mx_edi_fiscal_regime_ids
                ):
                    raise ValidationError(
                        self.env._(
                            "The default fiscal regime must be one of the allowed fiscal regimes for partner %s",
                            partner.name,
                        )
                    )

    @api.onchange("l10n_mx_edi_fiscal_regime_ids")
    def _onchange_l10n_mx_edi_fiscal_regime_ids(self):
        """Clear default fiscal regime if it's not in the allowed list."""
        if self.l10n_mx_edi_fiscal_regime_id and self.l10n_mx_edi_fiscal_regime_ids:
            if (
                self.l10n_mx_edi_fiscal_regime_id
                not in self.l10n_mx_edi_fiscal_regime_ids
            ):
                self.l10n_mx_edi_fiscal_regime_id = False
