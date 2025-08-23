import datetime

from odoo import api, fields, models


class StockLot(models.Model):
    """Inherit StockLot"""

    _inherit = "stock.lot"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    original_expiration_date = fields.Date(
        string="Original Expiration Date",
        help="Original expiration date before reconditioning",
        compute="_compute_original_expiration_date",
        store=True,
    )

    # Vehicle-related fields (migrated from fleet_vehicle.py)
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
    )

    fuel_card_id = fields.Many2one(
        comodel_name="documents.document",
        domain=lambda self: [
            ("tag_ids", "in", self.env.ref("marin_data.documents_fleet_fuel_card").ids),
        ],
        inverse="_inverse_fuel_card_id",
        store=True,
        readonly=False,
    )
    fuel_card_name = fields.Char(
        compute="_compute_fuel_card_name",
        store=True,
    )
    fuel_card_openning_balance = fields.Float(
        digits="Product Price",
        default=0.0,
        help="Opening balaned used to match the actual balance due differences caused by "
        "missing transactions and legacy data",
    )
    fuel_card_budget = fields.Float(
        string="Monthly fuel budget",
        digits="Product Price",
        default=0.0,
        help="Recommended starting balance for the fuel card at the beginning of the period",
    )
    fuel_card_balance = fields.Float(
        digits="Product Price",
        compute="_compute_fuel_card_balance",
        store=True,
        help="Current balance available on fuel card",
    )
    fuel_card_balance_to_reload = fields.Float(
        digits="Product Price",
        compute="_compute_fuel_card_balance_to_reload",
        store=True,
        help="Amount required to reach the recommended fuel card balance.",
    )
    fuel_card_count = fields.Integer(
        "Fuel",
        compute="_compute_fuel_card_count",
    )
    highway_pass_id = fields.Many2one(
        comodel_name="documents.document",
        domain=lambda self: [
            (
                "tag_ids",
                "in",
                self.env.ref("marin_data.documents_fleet_highway_pass").ids,
            ),
        ],
        inverse="_inverse_highway_pass_id",
        store=True,
        readonly=False,
    )
    highway_pass_name = fields.Char(
        compute="_compute_highway_pass_name",
        store=True,
    )
    highway_pass_openning_balance = fields.Float(
        digits="Product Price",
        default=0.0,
        help="Opening balaned used to match the actual balance due differences caused by "
        "missing transactions and legacy data",
    )
    highway_pass_budget = fields.Float(
        string="Monthly highway pass budget",
        digits="Product Price",
        default=0.0,
        help="Estimated monthly budget for toll usage",
    )
    highway_pass_balance = fields.Float(
        string="Current higway pass balance",
        digits="Product Price",
        compute="_compute_highway_pass_balance",
        store=True,
        help="Current available amount in the toll card",
    )
    highway_pass_balance_to_reload = fields.Float(
        string="Toll Balance to Reload",
        digits="Product Price",
        compute="_compute_highway_pass_balance_to_reload",
        store=True,
        help="Amount needed to reach the monthly toll budget",
    )
    highway_pass_count = fields.Integer(
        "Highway Pass",
        compute="_compute_highway_pass_count",
    )

    l10n_mx_vehicle_code = fields.Char(
        string="Vehicle Code",
        tracking=True,
        help="In Mexico the tax authority assign a 7 character code to identify its characteristics.",
    )
    account_prefix = fields.Char(
        string="Account Prefix",
        tracking=True,
        help="This fields is required by Accounting to group according to its needs.",
    )
    brand_new = fields.Boolean(
        string="Brand New",
        default=True,
        help="Mark as True if this vehicle was acquired as brand new.",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("product_id")
    def _compute_expiration_date(self):
        self.expiration_date = False
        for lot in self:
            if lot.product_id.use_expiration_date and not lot.expiration_date:
                product_tmpl = lot.product_id.product_tmpl_id
                duration = (
                    product_tmpl.expiration_time
                    or product_tmpl.categ_id.expiration_time
                )
                lot.expiration_date = datetime.datetime.now() + datetime.timedelta(
                    days=duration
                )

    @api.depends("product_id", "expiration_date")
    def _compute_dates(self):
        for lot in self:
            if not lot.product_id.use_expiration_date:
                lot.use_date = False
                lot.removal_date = False
                lot.alert_date = False
            elif lot.expiration_date:
                # when create
                if (
                    lot.product_id != lot._origin.product_id
                    or (
                        not lot.use_date and not lot.removal_date and not lot.alert_date
                    )
                    or (lot.expiration_date and not lot._origin.expiration_date)
                ):
                    product_tmpl = lot.product_id.product_tmpl_id
                    categ = product_tmpl.categ_id
                    lot.use_date = lot.expiration_date - datetime.timedelta(
                        days=product_tmpl.use_time or categ.use_time
                    )
                    lot.removal_date = lot.expiration_date - datetime.timedelta(
                        days=product_tmpl.removal_time or categ.removal_time
                    )
                    lot.alert_date = lot.expiration_date - datetime.timedelta(
                        days=product_tmpl.alert_time or categ.alert_time
                    )
                # when change
                elif lot._origin.expiration_date:
                    time_delta = lot.expiration_date - lot._origin.expiration_date
                    lot.use_date = (
                        lot._origin.use_date and lot._origin.use_date + time_delta
                    )
                    lot.removal_date = (
                        lot._origin.removal_date
                        and lot._origin.removal_date + time_delta
                    )
                    lot.alert_date = (
                        lot._origin.alert_date and lot._origin.alert_date + time_delta
                    )

    @api.depends("expiration_date")
    def _compute_original_expiration_date(self):
        """Compute original expiration date.

        If original_expiration_date is False, assign the value of expiration_date.
        If original_expiration_date already has a value, keep it unchanged.
        """
        for lot in self:
            if not lot.original_expiration_date and lot.expiration_date:
                lot.original_expiration_date = lot.expiration_date

    # Vehicle compute methods (migrated from fleet_vehicle.py)
    def _compute_fuel_card_count(self):
        fuel_product_category = self.env.ref("marin.product_category_fuel")
        for asset in self:
            if asset.asset_type == 'vehicle':
                asset.fuel_card_count = len(
                    asset.log_ids.filtered(
                        lambda l: l.product_category_id == fuel_product_category
                    )
                )
            else:
                asset.fuel_card_count = 0

    def _compute_highway_pass_count(self):
        highway_pass_product_category = self.env.ref(
            "marin.product_category_highway_toll"
        )
        for asset in self:
            if asset.asset_type == 'vehicle':
                asset.highway_pass_count = len(
                    asset.log_ids.filtered(
                        lambda l: l.product_category_id == highway_pass_product_category
                    )
                )
            else:
                asset.highway_pass_count = 0

    @api.depends("fuel_card_id")
    def _compute_fuel_card_name(self):
        for asset in self:
            name = ""
            if asset.fuel_card_id:
                name = asset.fuel_card_id.name.split(".", 1)[0]
                name = name.replace("Efecticard ", "")
            asset.fuel_card_name = name

    @api.depends("highway_pass_id")
    def _compute_highway_pass_name(self):
        for asset in self:
            name = ""
            if asset.highway_pass_id:
                name = asset.highway_pass_id.name.split(".", 1)[0]
                name = name.replace("IMDM ", "")
            asset.highway_pass_name = name

    @api.depends("log_ids.amount", "log_ids.state")
    def _compute_fuel_card_balance(self):
        """Calculates the current balance based on fuel credit/debit records"""
        fuel_product_category = self.env.ref("marin.product_category_fuel")
        for asset in self:
            if asset.asset_type == 'vehicle':
                # Find all fuel log records associated with this asset (only done state)
                fuel_logs = self.env["product.asset.log"].search(
                    [
                        ("asset_id", "=", asset.id),
                        ("product_category_id", "=", fuel_product_category.id),
                        ("state", "=", "done"),
                    ]
                )

                # Sum all movements (positive credits, negative debits)
                asset.fuel_card_balance = (
                    asset.fuel_card_openning_balance
                    + sum(fuel_logs.mapped("amount")) * -1
                )  # logs are considered cost of the vehicle, the balance in favor is negative
            else:
                asset.fuel_card_balance = 0.0

    @api.depends("log_ids.amount")
    def _compute_highway_pass_balance(self):
        """Compute current balance based on toll debit/credit records"""
        highway_pass_product_category = self.env.ref(
            "marin.product_category_highway_toll"
        )
        for asset in self:
            if asset.asset_type == 'vehicle':
                # Find all toll records associated with this asset
                highway_logs = self.env["product.asset.log"].search(
                    [
                        ("asset_id", "=", asset.id),
                        ("product_category_id", "=", highway_pass_product_category.id),
                    ]
                )

                # Sum all movements (positive credits, negative debits)
                asset.highway_pass_balance = (
                    asset.highway_pass_openning_balance
                    + sum(highway_logs.mapped("amount")) * -1
                )  # logs are considered cost of the vehicle, the balance in favor is negative
            else:
                asset.highway_pass_balance = 0.0

    @api.depends("fuel_card_budget", "fuel_card_balance")
    def _compute_fuel_card_balance_to_reload(self):
        """Calculates the balance that needs to be reloaded based on monthly load and current balance"""
        for asset in self:
            asset.fuel_card_balance_to_reload = max(
                0, asset.fuel_card_budget - asset.fuel_card_balance
            )

    @api.depends("highway_pass_budget", "highway_pass_balance")
    def _compute_highway_pass_balance_to_reload(self):
        """Compute the balance that needs to be reloaded based on monthly budget and current balance"""
        for asset in self:
            asset.highway_pass_balance_to_reload = max(
                0, asset.highway_pass_budget - asset.highway_pass_balance
            )

    # ------------------------------------------------------------
    # INVERSE METHODS
    # ------------------------------------------------------------

    def _inverse_fuel_card_id(self):
        """
        Set the vehicle on the corresponding document, and unset the vehicle on
        previously related documents
        """
        tag = self.env.ref("marin_data.documents_fleet_fuel_card", False)
        for asset in self:
            if asset.asset_type == 'vehicle':
                doc = asset.fuel_card_id
                other_docs = (
                    doc.search(
                        [("asset_id", "=", asset.id), ("tag_ids", "in", tag.ids)]
                    )
                    - doc
                )
                if doc:
                    doc.sudo().write(
                        {
                            "res_model": asset._name,
                            "res_id": asset.id,
                            "is_editable_attachment": True,
                            "asset_id": asset.id,
                        }
                    )
                for od in other_docs:
                    od.sudo().write(
                        {
                            "res_model": od._name,
                            "res_id": od.id,
                            "asset_id": False,
                        }
                    )

    def _inverse_highway_pass_id(self):
        """
        Set the vehicle on the corresponding document, and unset the vehicle on
        previously related documents
        """
        tag = self.env.ref("marin_data.documents_fleet_highway_pass", False)
        for asset in self:
            if asset.asset_type == 'vehicle':
                doc = asset.highway_pass_id
                other_docs = (
                    doc.search(
                        [("asset_id", "=", asset.id), ("tag_ids", "in", tag.ids)]
                    )
                    - doc
                )
                if doc:
                    doc.sudo().write(
                        {
                            "res_model": asset._name,
                            "res_id": asset.id,
                            "is_editable_attachment": True,
                            "asset_id": asset.id,
                        }
                    )
                for od in other_docs:
                    od.sudo().write(
                        {
                            "res_model": od._name,
                            "res_id": od.id,
                            "asset_id": False,
                        }
                    )

    # ------------------------------------------------------------
    #  ACTIONS
    # ------------------------------------------------------------

    def action_view_fuel_logs(self):
        self.ensure_one()
        fuel_product_category = self.env.ref("marin.product_category_fuel")
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "product_asset.action_product_asset_log"
        )
        action["domain"] = [
            ("asset_id", "=", self.id),
            ("product_category_id", "=", fuel_product_category.id),
        ]
        action["context"] = {
            "default_asset_id": self.id,
            "default_product_category_id": fuel_product_category.id,
            "hide_product_category": True,
            "show_vendor": True,
            "search_default_groupby_product_category_id": False,
        }
        return action

    def action_view_highway_pass_logs(self):
        self.ensure_one()
        highway_pass_product_category = self.env.ref(
            "marin.product_category_highway_toll"
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "product_asset.action_product_asset_log"
        )
        action["domain"] = [
            ("asset_id", "=", self.id),
            ("product_category_id", "=", highway_pass_product_category.id),
        ]
        action["context"] = {
            "default_asset_id": self.id,
            "default_product_category_id": highway_pass_product_category.id,
            "hide_product_category": True,
            "show_vendor": True,
            "search_default_groupby_product_category_id": False,
        }
        return action
