from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.sql import SQL


class PosConfig(models.Model):
    """Inherit PosConfig"""

    _inherit = "pos.config"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    active = fields.Boolean(default=True)
    load_all_partners_by_company = fields.Boolean(
        string="Load All Partners by Company",
        default=False,
        help="If enabled, all customers filtered by company will be loaded instead of using limited scroll-based loading.",
    )

    def action_liquidity_transfer(self):
        self.ensure_one()
        if self.has_active_session:
            raise UserError(
                _("Liquidity transfer is only allowed when there is no active session.")
            )
        session = self.env["pos.session"].search(
            [
                ("config_id", "=", self.id),
                ("state", "=", "closed"),
                ("rescue", "=", False),
            ],
            order="id desc",
            limit=1,
        )
        cash_journal = self.payment_method_ids.journal_id.filtered(
            lambda j: j.type == "cash"
        )[:1]
        action = {
            "name": _("POS Cash Transfer"),
            "type": "ir.actions.act_window",
            "res_model": "pos.cash.transfer.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("marin.wizard_pos_cash_transfer_form_view").id,
            "target": "new",
            "context": {
                "default_session_id": session.id,
                "default_journal_id": cash_journal.id,
                "default_currency_id": cash_journal.currency_id.id
                or cash_journal.company_id.currency_id.id,
                "default_amount": session.cash_register_balance_end_real,
            },
        }
        return action

    def _get_limited_partner_count(self):
        if self.load_all_partners_by_company:
            return self.env["res.partner"].search_count(
                [("company_id", "=", self.company_id.id)]
            )
        return super()._get_limited_partner_count()

    def get_limited_partners_loading(self, offset=0):
        if self.load_all_partners_by_company:
            return self.env.execute_query(
                SQL(
                    """
                WITH pm AS (
                    SELECT partner_id, COUNT(partner_id) AS order_count
                    FROM pos_order
                    GROUP BY partner_id
                )
                SELECT id
                FROM res_partner AS partner
                LEFT JOIN pm ON partner.id = pm.partner_id
                WHERE (partner.company_id = %s OR partner.company_id IS NULL)
                ORDER BY CASE WHEN partner.company_id IS NOT NULL THEN 0 ELSE 1 END,
                         COALESCE(pm.order_count, 0) DESC,
                         name
                LIMIT %s OFFSET %s
            """,
                    self.company_id.id,
                    self._get_limited_partner_count(),
                    offset,
                )
            )
        return super().get_limited_partners_loading(offset)
