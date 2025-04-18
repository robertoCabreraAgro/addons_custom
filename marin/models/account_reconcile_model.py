import re

from odoo import models, tools


class AccountReconcileModel(models.Model):
    """Inherit AccountReconcileModel"""

    _inherit = "account.reconcile.model"

    def _get_partner_from_mapping(self, st_line):
        """Find partner with mapping defined on model.
        For invoice matching rules, matches the statement line against each
        regex defined in partner mapping, and returns the partner corresponding
        to the first one matching.

        :param st_line (Model<account.bank.statement.line>):
        The statement line that needs a partner to be found
        :return Model<res.partner>:
        The partner found from the mapping. Can be empty an empty recordset
        if there was nothing found from the mapping or if the function is
        not applicable."""
        self.ensure_one()

        if self.rule_type not in ("invoice_matching", "writeoff_suggestion"):
            return self.env["res.partner"]

        for partner_mapping in self.partner_mapping_line_ids:
            match_payment_ref = match_narration = False

            if partner_mapping.payment_ref_regex:
                match_payment_ref = (
                    re.match(
                        partner_mapping.payment_ref_regex,
                        st_line.payment_ref,
                    )
                    if st_line.payment_ref
                    else False
                )

            if partner_mapping.narration_regex:
                match_narration = re.match(
                    partner_mapping.narration_regex,
                    tools.html2plaintext(st_line.narration or "").rstrip(),
                    flags=re.DOTALL,  # Ignore '/n' set by online sync.
                )

            if match_payment_ref or match_narration:
                return partner_mapping.partner_id

        return self.env["res.partner"]
