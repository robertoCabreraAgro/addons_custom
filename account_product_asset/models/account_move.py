from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    asset_ids = fields.Many2many(
        comodel_name="stock.lot",
        string="Assets",
        compute="_compute_asset_ids",
        help="Assets associated with this accounting move",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_asset_ids(self):
        """Compute assets from move lines."""
        for move in self:
            move.asset_ids = move.line_ids.mapped("asset_id")
