from . import models


def post_init_hook(env):
    """Post-install hook to migrate existing fiscal regime data from selection field to Many2one."""
    # Get all partners with fiscal regime data
    partners = env["res.partner"].search([("l10n_mx_edi_fiscal_regime", "!=", False)])

    for partner in partners:
        fiscal_regime_code = partner.l10n_mx_edi_fiscal_regime

        # Find the corresponding fiscal regime record
        fiscal_regime = env["l10n_mx_edi.fiscal.regime"].search([("code", "=", fiscal_regime_code)], limit=1)

        if fiscal_regime:
            # Update the partner with the new Many2one field
            partner.write(
                {
                    "l10n_mx_edi_fiscal_regime_id": fiscal_regime.id,
                    "l10n_mx_edi_fiscal_regime_ids": [(6, 0, [fiscal_regime.id])],
                }
            )

    # Update account moves if they have the old fiscal regime field
    # moves_with_fiscal_regime = env["account.move"].search(
    #    [("partner_id.l10n_mx_edi_fiscal_regime", "!=", False), ("move_type", "in", ["out_invoice", "out_refund"])]
    # )

    # for move in moves_with_fiscal_regime:
    #    if move.partner_id.l10n_mx_edi_fiscal_regime_id:
    #        move.write({"l10n_mx_edi_fiscal_regime_id": move.partner_id.l10n_mx_edi_fiscal_regime_id.id})
