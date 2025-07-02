from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.translate import _


class StockQuant(models.Model):
    """Inherit StockQuant"""

    _inherit = "stock.quant"

    # Extend core fields
    warehouse_id = fields.Many2one(
        store=True,
        readonly=True,
    )
    product_categ_id = fields.Many2one(
        store=True,
        readonly=True,
    )

    # New fields
    value_standard = fields.Monetary(
        "Value standard",
        compute="_compute_value_standard",
        store=True,
        groups="stock.group_stock_manager",
    )
    removal_priority = fields.Integer(
        related="location_id.removal_priority",
        store=True,
    )
    is_reconditioned = fields.Boolean(
        related="lot_id.is_reconditioned",
        string="Reconditioned",
        help="Indicates if this lot has been reconditioned to extend its shelf life",
    )
    recondition_date = fields.Date(
        related="lot_id.recondition_date",
        string="Recondition Date",
        help="Date when the product was reconditioned",
    )
    original_expiration_date = fields.Date(
        related="lot_id.original_expiration_date",
        string="Original Expiration Date",
        help="Original expiration date before reconditioning",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("company_id", "location_id", "owner_id", "product_id", "quantity")
    def _compute_value_standard(self):
        for quant in self:
            if quant.cost_method == "standard":
                quant.value_standard = quant.product_id.standard_price * quant.quantity
            else:
                quant.value_standard = 0.0

    # ------------------------------------------------------------
    # ACTION METHODS
    # ------------------------------------------------------------

    # Extend original method
    def _apply_inventory(self):
        self._can_apply_inventory()
        super()._apply_inventory()

    def action_stock_quant_lot_update(self):
        if len(self.company_id) > 1 or any(not q.company_id.id for q in self):
            raise UserError(_("You can only change lots used by a single company."))

        if len(self) > 1:
            raise UserError(_("You can only change lot of one quant at a time."))

        action = self.env["ir.actions.act_window"]._for_xml_id(
            "marin.action_stock_quant_lot_update"
        )
        action["context"] = {"active_model": self._name, "active_ids": self.ids}
        return action

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    # Extend original method
    @api.model
    def _get_removal_strategy(self, product_id, location_id):
        if (
            not product_id.categ_id.removal_strategy_id
            and not location_id.removal_strategy_id
        ):
            return "refurbished + fefo + priority"
        return super()._get_removal_strategy(product_id, location_id)

    # Extend original method
    @api.model
    def _get_removal_strategy_order(self, removal_strategy):
        if removal_strategy == "fifo + priority":
            return "in_date ASC, removal_priority ASC, id"

        if removal_strategy == "lifo + priority":
            return "in_date DESC, removal_priority ASC, id DESC"

        if removal_strategy == "fefo + priority":
            return "removal_date, removal_priority ASC, id"

        if removal_strategy == "refurbished + fefo + priority":
            return "is_reconditioned DESC, original_expiration_date ASC, removal_date, removal_priority ASC, id"

        return super()._get_removal_strategy_order(removal_strategy)

    def _get_gather_domain(
        self,
        product_id,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=False,
    ):
        domain = super()._get_gather_domain(
            product_id, location_id, lot_id, package_id, owner_id, strict
        )
        if not self.env.user.has_group(
            "stock_blocked_location.group_stock_force_blocked_location_in"
        ):
            domain = expression.AND(
                [[("location_id.block_outgoing", "=", False)], domain]
            )

        return domain

    def _gather(
        self,
        product_id,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=False,
        qty=0,
    ):
        ctx = dict(self.env.context)
        if self.env.context.get("with_expiration"):
            ctx.pop("with_expiration", None)

        return super(StockQuant, self.with_context(ctx))._gather(
            product_id,
            location_id,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
            qty=qty,
        )

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------

    def _can_apply_inventory(self):
        if not self.env.user.has_group("marin.group_stock_inventory_adjustment"):
            raise UserError(
                _("Only a inventory manager can validate an inventory adjustment.")
            )
