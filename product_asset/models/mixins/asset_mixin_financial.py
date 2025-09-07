import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AssetMixinFinancial(models.AbstractModel):
    """Financial mixin for asset management

    This mixin handles all financial aspects of assets including:
    - Asset valuation (original and residual values)
    - Fuel card management (budgets, balances, reloads)
    - Highway pass/toll card management
    - Financial tracking and reporting
    """

    _name = "asset.mixin.financial"
    _description = "Asset Financial Mixin"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    value_original = fields.Float(
        string="Original Value (VAT Incl.)",
        copy=False,
        tracking=True,
        help="Original purchase value of the asset including VAT",
    )
    value_residual = fields.Float(
        string="Residual Value",
        copy=False,
        help="Current residual value of the asset after depreciation",
    )
    account_prefix = fields.Char(
        string="Account Prefix",
        tracking=True,
        help="Accounting prefix used to group assets for financial reporting",
    )

    # ------------------------------------------------------------
    # FUEL CARD MANAGEMENT FIELDS
    # ------------------------------------------------------------

    fuel_card_id = fields.Many2one(
        comodel_name="res.partner",
        string="Fuel Card",
        domain="[('supplier_rank', '>', 0)]",
        help="Fuel card provider/account for this asset",
    )

    fuel_card_name = fields.Char(
        string="Fuel Card Name",
        compute="_compute_fuel_card_name",
        help="Formatted name of the fuel card",
    )

    fuel_card_budget = fields.Float(
        string="Monthly Fuel Budget",
        digits="Product Price",
        default=0.0,
        help="Recommended monthly fuel budget for this asset",
    )

    fuel_card_openning_balance = fields.Float(
        string="Fuel Card Opening Balance",
        digits="Product Price",
        default=0.0,
        help="Opening balance for fuel card reconciliation",
    )

    fuel_card_balance = fields.Float(
        string="Fuel Card Balance",
        digits="Product Price",
        compute="_compute_fuel_card_balance",
        store=True,
        help="Current available balance on the fuel card",
    )

    fuel_card_balance_to_reload = fields.Float(
        string="Fuel Amount to Reload",
        digits="Product Price",
        compute="_compute_fuel_card_balance_to_reload",
        store=True,
        help="Amount needed to reach the monthly fuel budget",
    )

    # ------------------------------------------------------------
    # HIGHWAY PASS / TOLL CARD FIELDS
    # ------------------------------------------------------------

    highway_pass_id = fields.Many2one(
        comodel_name="res.partner",
        string="Highway Pass",
        domain="[('supplier_rank', '>', 0)]",
        help="Highway pass/toll card provider for this asset",
    )

    highway_pass_name = fields.Char(
        string="Highway Pass Name",
        compute="_compute_highway_pass_name",
        help="Formatted name of the highway pass",
    )

    highway_pass_budget = fields.Float(
        string="Monthly Highway Pass Budget",
        digits="Product Price",
        default=0.0,
        help="Estimated monthly budget for toll/highway pass usage",
    )

    highway_pass_openning_balance = fields.Float(
        string="Highway Pass Opening Balance",
        digits="Product Price",
        default=0.0,
        help="Opening balance for highway pass reconciliation",
    )

    highway_pass_balance = fields.Float(
        string="Highway Pass Balance",
        digits="Product Price",
        compute="_compute_highway_pass_balance",
        store=True,
        help="Current available balance on the highway pass",
    )

    highway_pass_balance_to_reload = fields.Float(
        string="Highway Pass Amount to Reload",
        digits="Product Price",
        compute="_compute_highway_pass_balance_to_reload",
        store=True,
        help="Amount needed to reach the monthly highway pass budget",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("fuel_card_id")
    def _compute_fuel_card_name(self):
        """Extract and format fuel card name from partner"""
        for asset in self:
            try:
                name = ""
                if asset.fuel_card_id:
                    # Extract card name, removing common prefixes
                    name = asset.fuel_card_id.name.split(".", 1)[0]
                    name = name.replace("Efecticard ", "").replace("Card ", "")
                asset.fuel_card_name = name
            except Exception as e:
                _logger.warning(
                    f"Error computing fuel card name for asset {asset.id}: {e}"
                )
                asset.fuel_card_name = ""

    @api.depends("highway_pass_id")
    def _compute_highway_pass_name(self):
        """Extract and format highway pass name from partner"""
        for asset in self:
            try:
                name = ""
                if asset.highway_pass_id:
                    # Extract pass name, removing common prefixes
                    name = asset.highway_pass_id.name.split(".", 1)[0]
                    name = name.replace("IMDM ", "").replace("Pass ", "")
                asset.highway_pass_name = name
            except Exception as e:
                _logger.warning(
                    f"Error computing highway pass name for asset {asset.id}: {e}"
                )
                asset.highway_pass_name = ""

    @api.depends("log_ids.state", "log_ids.amount")
    def _compute_fuel_card_balance(self):
        """Calculate current fuel card balance based on transaction logs"""
        # Try to get fuel product category reference
        try:
            fuel_product_category = self.env.ref(
                "product_asset.product_category_fuel", False
            )
        except Exception as e:
            _logger.warning(f"Error getting fuel product category: {e}")
            fuel_product_category = False

        # If category doesn't exist during installation, use opening balance
        if not fuel_product_category:
            for asset in self:
                asset.fuel_card_balance = asset.fuel_card_openning_balance
            return

        for asset in self:
            try:
                # Find all fuel log records for this asset (only completed)
                fuel_logs = self.env["product.asset.log"].search(
                    [
                        ("asset_id", "=", asset.id),
                        ("product_category_id", "=", fuel_product_category.id),
                        ("state", "=", "done"),
                    ]
                )

                # Calculate balance: opening + sum of transactions
                # Negative because logs represent costs/expenses
                asset.fuel_card_balance = (
                    asset.fuel_card_openning_balance
                    + sum(fuel_logs.mapped("amount")) * -1
                )
            except Exception as e:
                _logger.warning(
                    f"Error computing fuel card balance for asset {asset.id}: {e}"
                )
                asset.fuel_card_balance = asset.fuel_card_openning_balance

    @api.depends("log_ids.state", "log_ids.amount")
    def _compute_highway_pass_balance(self):
        """Calculate current highway pass balance based on transaction logs"""
        # Try to get highway toll product category reference
        try:
            highway_pass_product_category = self.env.ref(
                "product_asset.product_category_highway_toll", False
            )
        except Exception as e:
            _logger.warning(f"Error getting highway toll product category: {e}")
            highway_pass_product_category = False

        # If category doesn't exist during installation, use opening balance
        if not highway_pass_product_category:
            for asset in self:
                asset.highway_pass_balance = asset.highway_pass_openning_balance
            return

        for asset in self:
            try:
                # Find all highway toll log records for this asset (only completed)
                highway_logs = self.env["product.asset.log"].search(
                    [
                        ("asset_id", "=", asset.id),
                        ("product_category_id", "=", highway_pass_product_category.id),
                        ("state", "=", "done"),
                    ]
                )

                # Calculate balance: opening + sum of transactions
                # Negative because logs represent costs/expenses
                asset.highway_pass_balance = (
                    asset.highway_pass_openning_balance
                    + sum(highway_logs.mapped("amount")) * -1
                )
            except Exception as e:
                _logger.warning(
                    f"Error computing highway pass balance for asset {asset.id}: {e}"
                )
                asset.highway_pass_balance = asset.highway_pass_openning_balance

    @api.depends("fuel_card_budget", "fuel_card_balance")
    def _compute_fuel_card_balance_to_reload(self):
        """Calculate amount needed to reach fuel budget"""
        for asset in self:
            try:
                # Calculate reload amount: budget - current balance
                # Only positive values (no negative reload)
                asset.fuel_card_balance_to_reload = max(
                    0, asset.fuel_card_budget - asset.fuel_card_balance
                )
            except Exception as e:
                _logger.warning(
                    f"Error computing fuel reload amount for asset {asset.id}: {e}"
                )
                asset.fuel_card_balance_to_reload = 0

    @api.depends("highway_pass_budget", "highway_pass_balance")
    def _compute_highway_pass_balance_to_reload(self):
        """Calculate amount needed to reach highway pass budget"""
        for asset in self:
            try:
                # Calculate reload amount: budget - current balance
                # Only positive values (no negative reload)
                asset.highway_pass_balance_to_reload = max(
                    0, asset.highway_pass_budget - asset.highway_pass_balance
                )
            except Exception as e:
                _logger.warning(
                    f"Error computing highway reload amount for asset {asset.id}: {e}"
                )
                asset.highway_pass_balance_to_reload = 0

    # ------------------------------------------------------------
    # HELPER METHODS
    # ------------------------------------------------------------

    def get_total_asset_cost(self):
        """Calculate total cost of ownership for the asset"""
        self.ensure_one()

        total_cost = self.value_original or 0.0

        # Add all completed service/maintenance costs
        service_logs = self.log_ids.filtered(
            lambda l: l.state == "done" and l.amount > 0
        )
        total_cost += sum(service_logs.mapped("amount"))

        return total_cost

    def get_depreciation_info(self):
        """Get depreciation information for the asset"""
        self.ensure_one()

        depreciation = 0.0
        if self.value_original and self.value_residual:
            depreciation = self.value_original - self.value_residual

        return {
            "original_value": self.value_original,
            "residual_value": self.value_residual,
            "depreciation": depreciation,
            "depreciation_rate": (
                (depreciation / self.value_original * 100) if self.value_original else 0
            ),
        }
