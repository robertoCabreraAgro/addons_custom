from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductAssetLog(models.Model):
    _inherit = "product.asset.log"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    account_move_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Accounting Entry",
    )
    account_move_state = fields.Selection(
        related="account_move_line_id.parent_state",
        string="Bill State",
    )
    asset_id = fields.Many2one(
        compute="_compute_asset_id",
        store=True,
        readonly=False,
    )
    amount = fields.Monetary(
        compute="_compute_amount",
        store=True,
        inverse="_inverse_amount",
        readonly=False,
    )

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    @api.ondelete(at_uninstall=False)
    def _unlink_if_no_linked_bill(self):
        """Prevent deletion of logs linked to bills."""
        if self.env.context.get("ignore_linked_bill_constraint"):
            return
        if any(log.account_move_line_id for log in self):
            raise UserError(
                _(
                    "You cannot delete log services records because one or more of them were created from a bill."
                )
            )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("account_move_line_id.asset_id")
    def _compute_asset_id(self):
        """Update asset from the linked accounting line."""
        for log in self:
            # We avoid emptying the asset_id as it is a required field
            if not log.account_move_line_id.asset_id:
                continue
            log.asset_id = log.account_move_line_id.asset_id

    @api.depends("account_move_line_id.price_subtotal")
    def _compute_amount(self):
        """Compute amount from the linked accounting line."""
        for log in self:
            log.amount = log.account_move_line_id.debit

    # ------------------------------------------------------------
    # INVERSE METHODS
    # ------------------------------------------------------------

    def _inverse_amount(self):
        """Prevent modification of amount for logs linked to accounting entries."""
        if any(service.account_move_line_id for service in self):
            raise UserError(
                _(
                    "You cannot modify amount of services linked to an account move line. "
                    "Do it on the related accounting entry instead."
                )
            )

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_open_account_move(self):
        """Open the related accounting move."""
        self.ensure_one()
        return {
            "name": _("Bill"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "target": "current",
            "res_id": self.account_move_line_id.move_id.id,
        }
