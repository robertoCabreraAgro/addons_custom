from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    emitter_fiscal_regime = fields.Many2one(
        "l10n_mx_edi.fiscal.regime",
        string="Emitter Fiscal Regime",
        domain="[('id', 'in', company_id.partner_id.allowed_fiscal_regimes.ids)]",
        compute="_compute_emitter_fiscal_regime",
        store=True,
        readonly=True,
        required=True,
    )

    l10n_mx_edi_fiscal_regime_id = fields.Many2one(
        "l10n_mx_edi.fiscal.regime",
        string="Fiscal Regime",
        help="Fiscal regime to be used for this invoice CFDI generation",
        domain="[('id', 'in', l10n_mx_edi_fiscal_regime_ids)]",
        compute="_compute_l10n_mx_edi_fiscal_regime_id",
        store=True,
        readonly=False,
    )

    l10n_mx_edi_fiscal_regime_ids = fields.Many2many(
        "l10n_mx_edi.fiscal.regime", compute="_compute_l10n_mx_edi_fiscal_regime_ids"
    )

    @api.depends("journal_id")
    def _compute_emitter_fiscal_regime(self):
        for move in self:
            move.emitter_fiscal_regime = move.journal_id.default_emitter_fiscal_regime

    @api.depends("partner_id", "partner_id.l10n_mx_edi_fiscal_regime_ids")
    def _compute_l10n_mx_edi_fiscal_regime_ids(self):
        """Compute the allowed fiscal regimes based on partner configuration."""
        for move in self:
            if move.partner_id and move.partner_id.l10n_mx_edi_fiscal_regime_ids:
                move.l10n_mx_edi_fiscal_regime_ids = move.partner_id.l10n_mx_edi_fiscal_regime_ids
            else:
                move.l10n_mx_edi_fiscal_regime_ids = self.env["l10n_mx_edi.fiscal.regime"]

    @api.depends("partner_id", "partner_id.l10n_mx_edi_fiscal_regime_id")
    def _compute_l10n_mx_edi_fiscal_regime_id(self):
        """Auto-populate fiscal regime from partner's fiscal regime when partner changes."""
        for move in self:
            if move.partner_id and move.partner_id.l10n_mx_edi_fiscal_regime_id:
                # Only set if not already set or if partner changed
                if not move.l10n_mx_edi_fiscal_regime_id or move._origin.partner_id != move.partner_id:
                    move.l10n_mx_edi_fiscal_regime_id = move.partner_id.l10n_mx_edi_fiscal_regime_id
            elif not move.partner_id:
                move.l10n_mx_edi_fiscal_regime_id = False

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Update fiscal regime when partner changes."""
        res = super()._onchange_partner_id()
        l10n_mx_edi_fiscal_regime_id = False
        if self.partner_id and self.partner_id.l10n_mx_edi_fiscal_regime_id:
            l10n_mx_edi_fiscal_regime_id = self.partner_id.l10n_mx_edi_fiscal_regime_id
        self.l10n_mx_edi_fiscal_regime_id = l10n_mx_edi_fiscal_regime_id
        return res

    @api.onchange("journal_id")
    def _onchange_journal_id_emitter(self):
        if self.journal_id:
            self.emitter_fiscal_regime = self.journal_id.default_emitter_fiscal_regime

    def _l10n_mx_edi_get_customer_fiscal_regime(self):
        """Helper method to return the selected fiscal regime for CFDI generation.
        This method should be called by the EDI process to get the fiscal regime.
        """
        self.ensure_one()
        if self.move_type in ["out_invoice", "out_refund"]:
            if self.l10n_mx_edi_fiscal_regime_id:
                return self.l10n_mx_edi_fiscal_regime_id.code
            if self.partner_id.l10n_mx_edi_fiscal_regime_id:
                return self.partner_id.l10n_mx_edi_fiscal_regime_id.code
            customer = self.partner_id or self.env["res.partner"]
            invoice_customer = customer if customer.type == "invoice" else customer.commercial_partner_id
            return invoice_customer.l10n_mx_edi_fiscal_regime or "616"
        return False

    def _l10n_mx_edi_get_emitter_fiscal_regime(self):
        self.ensure_one()
        if self.emitter_fiscal_regime:
            return self.emitter_fiscal_regime.code
        if self.journal_id.default_emitter_fiscal_regime:
            return self.journal_id.default_emitter_fiscal_regime.code
        company_partner = self.company_id.partner_id
        if company_partner.l10n_mx_edi_fiscal_regime_id:
            return company_partner.l10n_mx_edi_fiscal_regime_id.code
        return company_partner.l10n_mx_edi_fiscal_regime

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values):
        """Include the selected fiscal regime in CFDI values."""
        res = super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values)
        customer_values = cfdi_values["receptor"]

        # Update fiscal regime for customer in CFDI values
        customer_fiscal_regime_code = self._l10n_mx_edi_get_customer_fiscal_regime()
        if customer_fiscal_regime_code and customer_values.get("regimen_fiscal_receptor"):
            customer_values["regimen_fiscal_receptor"] = customer_fiscal_regime_code
        cfdi_values.update({"receptor": customer_values})

        emitter_values = cfdi_values.get("emisor", {})
        emitter_code = self._l10n_mx_edi_get_emitter_fiscal_regime()
        if emitter_code and emitter_values.get("regimen_fiscal"):
            emitter_values["regimen_fiscal"] = emitter_code
        cfdi_values.update({"emisor": emitter_values})
        return res
