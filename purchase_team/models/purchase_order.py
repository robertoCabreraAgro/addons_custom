from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    team_id = fields.Many2one(
        "srm.team",
        "Purchases team",
        index=True,
        auto_join=True,
        compute="_compute_team_id",
        store=True,
        readonly=False,
    )

    @api.depends("user_id")
    def _compute_team_id(self):
        """When a user is assigned, the first team which the user belongs to is
        assigned, and if no one, the first purchase team.
        """
        first_team = self.env["srm.team"].search([], limit=1)
        for record in self:
            record.team_id = record.user_id.srm_team_ids[:1] or first_team

    def onchange_partner_id(self):
        res = super().onchange_partner_id()
        if self.partner_id:
            partner = self.partner_id.commercial_partner_id
            if not self.env.context.get("default_user_id"):
                self.user_id = partner.purchase_user_id or self.env.user
            if not self.env.context.get("default_team_id"):
                self.team_id = (
                    partner.purchase_team_id
                    or self.user_id.purchase_team_id
                    or self.env["srm.team"].search([], limit=1)
                )
        return res
