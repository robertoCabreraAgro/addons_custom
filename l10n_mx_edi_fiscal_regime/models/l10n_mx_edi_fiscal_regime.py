from odoo import api, fields, models


class L10nMxEdiFiscalRegime(models.Model):
    _name = "l10n_mx_edi.fiscal.regime"
    _description = "Mexican Fiscal Regime"
    _order = "code"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    name = fields.Char(
        required=True,
        help="Fiscal regime description",
    )
    active = fields.Boolean(
        default=True,
        help="Set to false to hide the fiscal regime without removing it",
    )
    code = fields.Char(
        required=True,
        size=3,
        help="SAT fiscal regime code",
    )

    # ------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------

    _fiscal_regime_code_uniq = models.Constraint(
        "UNIQUE(code)",
        "The fiscal regime code must be unique!",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("code", "name")
    def _compute_display_name(self):
        """Compute display name showing code and name."""
        for regime in self:
            regime.display_name = f"[{regime.code}] {regime.name}"
