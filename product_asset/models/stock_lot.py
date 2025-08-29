from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class StockLot(models.Model):
    """Inherit StockLot"""

    _inherit = "stock.lot"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    fuel_tank_capacity = fields.Integer(
        string="Tank capacity",
        related="product_id.fuel_tank_capacity",
        store=True,
        help="Fuel tank capacity in liters",
    )
    asset_type = fields.Selection(
        related="product_id.asset_type",
        store=True,
        string="Asset Type",
    )
    asset_manager_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Manager",
        domain=lambda self: [
            # ("groups_id", "in", self.env.ref("fleet.fleet_group_manager").id),
            ("company_id", "in", self.env.companies.ids),
        ],
    )
    operator_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Driver",
        domain='[("company_id", "in", (company_id, False))]',
        copy=False,
        tracking=True,
    )
    future_operator_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Future Driver",
        domain='[("company_id", "in", (company_id, False))]',
        copy=False,
        tracking=True,
    )
    location = fields.Char(
        help="Location of the asset (garage, ...)",
    )
    model_year = fields.Char(
        string="Model Year",
        help="Year of the model",
    )
    brand_new = fields.Boolean(
        string="Brand New",
        default=True,
        help="Mark as True if this asset was acquired as brand new.",
    )
    trailer_hook = fields.Boolean(
        string="Trailer Hitch",
        default=False,
    )

    # Identification fields
    license_plate = fields.Char(
        copy=False,
        tracking=True,
        help="License plate number of the asset (eg plate number for a car)",
    )
    vin_sn = fields.Char(
        string="Chassis SN",
        copy=False,
        tracking=True,
        help="Unique number written on an asset's chassis (VIN/SN number).",
    )
    engine_sn = fields.Char(
        string="Engine SN",
        copy=False,
        tracking=True,
        help="Unique number written on the asset's engine.",
    )

    # Financial fields
    date_acquisition = fields.Date(
        string="Registration Date",
        copy=False,
        tracking=True,
        help="Date of asset's registration",
    )
    date_write_off = fields.Date(
        string="Cancellation Date",
        copy=False,
        tracking=True,
        help="Date when the asset's license plate has been cancelled/removed.",
    )
    value_original = fields.Float(
        string="Catalog Value (VAT Incl.)",
        copy=False,
        tracking=True,
    )
    value_residual = fields.Float(
        copy=False,
    )
    account_prefix = fields.Char(
        string="Account Prefix",
        tracking=True,
        help="This fields is required by Accounting to group according to its needs.",
    )

    fuel_card_id = fields.Many2one(
        comodel_name="documents.document",
        inverse="_inverse_fuel_card_id",
        store=True,
        readonly=False,
    )
    fuel_card_name = fields.Char(
        compute="_compute_fuel_card_name",
        store=True,
    )
    count_fuel_card = fields.Integer(
        "Fuel cards count",
        compute="_compute_count_fuel_card",
    )
    fuel_card_budget = fields.Float(
        string="Monthly fuel budget",
        digits="Product Price",
        default=0.0,
        help="Recommended starting balance for the fuel card at the beginning of the period",
    )
    fuel_card_openning_balance = fields.Float(
        digits="Product Price",
        default=0.0,
        help="Opening balaned used to match the actual balance due differences caused by "
        "missing transactions and legacy data",
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
    highway_pass_id = fields.Many2one(
        comodel_name="documents.document",
        inverse="_inverse_highway_pass_id",
        store=True,
        readonly=False,
    )
    highway_pass_name = fields.Char(
        compute="_compute_highway_pass_name",
        store=True,
    )
    count_highway_pass = fields.Integer(
        "Highway passes count",
        compute="_compute_count_highway_pass",
    )
    highway_pass_budget = fields.Float(
        string="Monthly highway pass budget",
        digits="Product Price",
        default=0.0,
        help="Estimated monthly budget for toll usage",
    )
    highway_pass_openning_balance = fields.Float(
        digits="Product Price",
        default=0.0,
        help="Opening balaned used to match the actual balance due differences caused by "
        "missing transactions and legacy data",
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

    area = fields.Integer(
        string="Area",
        help="Area of the asset in square meters",
    )

    log_ids = fields.One2many(
        "product.asset.log",
        "asset_id",
        "Logs",
    )
    service_activity = fields.Selection(
        selection=[
            ("none", "None"),
            ("overdue", "Overdue"),
            ("today", "Today"),
        ],
        compute="_compute_service_activity",
        store=True,
    )
    odometer = fields.Float(
        string="Odometer",
        compute="_compute_odometer",
        readonly=True,
        help="Odometer measure of the asset",
    )
    odometer_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Odometer Unit",
        default=lambda self: self.env.ref("uom.product_uom_km", False),
        tracking=True,
        help="Unit of measurement for the odometer readings",
    )
    count_assignment = fields.Integer(
        string="Drivers History Count",
        compute="_compute_count_all",
    )
    count_contract = fields.Integer(
        string="Contracts",
        compute="_compute_count_all",
    )
    count_service = fields.Integer(
        string="Services",
        compute="_compute_count_all",
    )
    date_first_contract = fields.Date(
        string="First Contract Date",
        default=fields.Date.today,
        tracking=True,
    )
    date_next_assignation = fields.Date(
        string="Assignment Date",
        help="This is the date at which the car will be available, "
        "if not set it means available instantly",
    )
    contract_renewal_due_soon = fields.Boolean(
        string="Has Contracts to renew",
        compute="_compute_contract_reminder",
        search="_search_contract_renewal_due_soon",
        compute_sudo=False,
        store=True,
    )
    contract_renewal_overdue = fields.Boolean(
        string="Has Contracts Overdue",
        compute="_compute_contract_reminder",
        search="_search_get_overdue_contract_reminder",
        compute_sudo=False,
        store=True,
    )
    contract_state = fields.Selection(
        selection=[
            ("futur", "Incoming"),
            ("open", "In Progress"),
            ("expired", "Expired"),
            ("closed", "Closed"),
        ],
        string="Last Contract State",
        required=False,
        compute="_compute_contract_reminder",
        compute_sudo=False,
        store=True,
    )

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        lots = super().create(vals_list)
        for lot, vals in zip(lots, vals_list):
            if vals.get("operator_id"):
                lot.create_operator_assignment_log(vals)
        return lots

    def write(self, vals):
        if "operator_id" in vals and vals["operator_id"]:
            operator_id = vals["operator_id"]
            for lot in self.filtered(lambda v: v.operator_id.id != operator_id):
                lot.create_operator_assignment_log(vals)

        if "active" in vals and not vals["active"]:
            self.env["product.asset.log"].search(
                [("asset_id", "in", self.ids)]
            ).active = False

        res = super().write(vals)

        return res

    def _track_subtype(self, init_values):
        self.ensure_one()
        if "operator_id" in init_values or "future_operator_id" in init_values:
            return self.env.ref("product_asset.mt_asset_driver_updated")

        return super()._track_subtype(init_values)

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_count_fuel_card(self):
        fuel_card_product = self.env.ref(
            "product_asset.product_product_fuel_credit", False
        )
        if not fuel_card_product:
            for asset in self:
                asset.count_fuel_card = 0
            return

        for asset in self:
            asset.count_fuel_card = len(
                asset.log_ids.filtered(lambda l: l.product_id == fuel_card_product)
            )

    def _compute_count_highway_pass(self):
        highway_pass_product = self.env.ref(
            "product_asset.product_product_highway_credit", False
        )
        if not highway_pass_product:
            for asset in self:
                asset.count_highway_pass = 0
            return

        for asset in self:
            asset.count_highway_pass = len(
                asset.log_ids.filtered(lambda l: l.product_id == highway_pass_product)
            )

    def _compute_count_all(self):
        Log = self.env["product.asset.log"].with_context(active_test=False)

        # Get category references with fallback during installation
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies"
            )
            assignment_category = self.env.ref(
                "product_asset.product_category_maintenance_and_repairs"
            )
            service_categories = self.env.ref(
                "product_asset.product_category_fuel"
            ) + self.env.ref("product_asset.product_category_highway_toll")
        except ValueError:
            # During installation, external IDs may not be available yet
            for vehicle in self:
                vehicle.count_contract = 0
                vehicle.count_service = 0
                vehicle.count_assignment = 0
            return

        contract_data = Log._read_group(
            [
                ("asset_id", "in", self.ids),
                ("product_category_id", "=", contract_category.id),
                ("state", "!=", "closed"),
            ],
            ["asset_id", "active"],
            ["__count"],
        )
        service_data = Log._read_group(
            [
                ("asset_id", "in", self.ids),
                ("product_category_id", "in", service_categories.ids),
            ],
            ["asset_id", "active"],
            ["__count"],
        )
        history_data = Log._read_group(
            [
                ("asset_id", "in", self.ids),
                ("product_category_id", "=", assignment_category.id),
            ],
            ["asset_id"],
            ["__count"],
        )

        mapped_contract_data = defaultdict(lambda: defaultdict(lambda: 0))
        mapped_service_data = defaultdict(lambda: defaultdict(lambda: 0))
        mapped_history_data = defaultdict(lambda: 0)

        for vehicle, active, count in contract_data:
            mapped_contract_data[vehicle.id][active] = count
        for vehicle, active, count in service_data:
            mapped_service_data[vehicle.id][active] = count
        for vehicle, count in history_data:
            mapped_history_data[vehicle.id] = count

        for vehicle in self:
            vehicle.count_contract = mapped_contract_data[vehicle.id][vehicle.active]
            vehicle.count_service = mapped_service_data[vehicle.id][vehicle.active]
            vehicle.count_assignment = mapped_history_data[vehicle.id]

    @api.depends("model_id")
    def _compute_image_128(self):
        for product in self:
            if product.model_id:
                product.image_128 = product.manufacturer_id.image_128
            else:
                product.image_128 = product.image_1920

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

    @api.depends("log_ids")
    def _compute_service_activity(self):
        for asset in self:
            activities_state = set(
                state
                for state in asset.log_ids.mapped("activity_state")
                if state and state != "planned"
            )
            asset.service_activity = (
                sorted(activities_state)[0] if activities_state else "none"
            )

    @api.depends("log_ids.state", "log_ids.amount")
    def _compute_fuel_card_balance(self):
        """Calculates the current balance based on fuel credit/debit records"""
        fuel_product_category = self.env.ref(
            "product_asset.product_category_fuel", False
        )

        # If category doesn't exist during installation, set balance to opening balance
        if not fuel_product_category:
            for vehicle in self:
                vehicle.fuel_card_balance = vehicle.fuel_card_openning_balance
            return

        for vehicle in self:
            # Find all fuel log records associated with this vehicle (only done state)
            fuel_logs = self.env["product.asset.log"].search(
                [
                    ("asset_id", "=", vehicle.id),
                    ("product_category_id", "=", fuel_product_category.id),
                    ("state", "=", "done"),
                ]
            )

            # Sum all movements (positive credits, negative debits)
            vehicle.fuel_card_balance = (
                vehicle.fuel_card_openning_balance
                + sum(fuel_logs.mapped("amount")) * -1
            )  # logs are considered cost of the vehicle, the balance in favor is negative

    @api.depends("log_ids.state", "log_ids.amount")
    def _compute_highway_pass_balance(self):
        """Compute current balance based on toll debit/credit records"""
        highway_pass_product_category = self.env.ref(
            "product_asset.product_category_highway_toll", False
        )

        # If category doesn't exist during installation, set balance to opening balance
        if not highway_pass_product_category:
            for vehicle in self:
                vehicle.highway_pass_balance = vehicle.highway_pass_openning_balance
            return

        for vehicle in self:
            # Find all toll records associated with this vehicle
            highway_logs = self.env["product.asset.log"].search(
                [
                    ("asset_id", "=", vehicle.id),
                    ("product_category_id", "=", highway_pass_product_category.id),
                ]
            )

            # Sum all movements (positive credits, negative debits)
            vehicle.highway_pass_balance = (
                vehicle.highway_pass_openning_balance
                + sum(highway_logs.mapped("amount")) * -1
            )  # logs are considered cost of the vehicle, the balance in favor is negative

    @api.depends("fuel_card_budget", "fuel_card_balance")
    def _compute_fuel_card_balance_to_reload(self):
        """Calculates the balance that needs to be reloaded based on monthly load and current balance"""
        for vehicle in self:
            vehicle.fuel_card_balance_to_reload = max(
                0,
                vehicle.fuel_card_budget - vehicle.fuel_card_balance,
            )

    @api.depends("highway_pass_budget", "highway_pass_balance")
    def _compute_highway_pass_balance_to_reload(self):
        """Compute the balance that needs to be reloaded based on monthly budget and current balance"""
        for vehicle in self:
            vehicle.highway_pass_balance_to_reload = max(
                0,
                vehicle.highway_pass_budget - vehicle.highway_pass_balance,
            )

    @api.depends("log_ids")
    def _compute_contract_reminder(self):
        params = self.env["ir.config_parameter"].sudo()
        delay_alert_contract = int(
            params.get_param("hr_fleet.delay_alert_contract", default=30)
        )
        current_date = fields.Date.context_today(self)
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies"
            )
        except ValueError:
            # During installation, external IDs may not be available yet
            for vehicle in self:
                vehicle.contract_renewal_overdue = False
                vehicle.contract_renewal_due_soon = False
                vehicle.contract_state = ""
            return
        data = self.env["product.asset.log"]._read_group(
            domain=[
                ("asset_id", "in", self.ids),
                ("state", "!=", "closed"),
                ("date_end", "!=", False),
                ("product_category_id", "=", contract_category.id),
            ],
            groupby=["asset_id", "state"],
            aggregates=["date_end:max"],
        )
        prepared_data = {}
        for asset_id, state, date_end in data:
            if prepared_data.get(asset_id.id):
                if prepared_data[asset_id.id]["date_end"] < date_end:
                    prepared_data[asset_id.id]["date_end"] = date_end
                    prepared_data[asset_id.id]["state"] = state
            else:
                prepared_data[asset_id.id] = {
                    "state": state,
                    "date_end": date_end,
                }
        for asset in self:
            asset_data = prepared_data.get(asset.id)
            if asset_data:
                diff_time = (asset_data["date_end"] - current_date).days
                asset.contract_renewal_overdue = diff_time < 0
                asset.contract_renewal_due_soon = (
                    not asset.contract_renewal_overdue
                    and (diff_time < delay_alert_contract)
                )
                asset.contract_state = asset_data["state"]
            else:
                asset.contract_renewal_overdue = False
                asset.contract_renewal_due_soon = False
                asset.contract_state = ""

    @api.depends("log_ids", "log_ids.odometer")
    def _compute_odometer(self):
        for asset in self:
            if asset.log_ids:
                asset.odometer = max(asset.log_ids.mapped("odometer"))
            else:
                asset.odometer = 0.0

    # ------------------------------------------------------------
    # INVERSE METHODS
    # ------------------------------------------------------------

    def _inverse_fuel_card_id(self):
        """
        Set the asset on the corresponding document
        """
        for asset in self:
            doc = asset.fuel_card_id
            if doc:
                doc.sudo().write(
                    {
                        "res_model": asset._name,
                        "res_id": asset.id,
                        "is_editable_attachment": True,
                    }
                )

    def _inverse_highway_pass_id(self):
        """
        Set the asset on the corresponding document
        """
        for asset in self:
            doc = asset.highway_pass_id
            if doc:
                doc.sudo().write(
                    {
                        "res_model": asset._name,
                        "res_id": asset.id,
                        "is_editable_attachment": True,
                    }
                )

    # ------------------------------------------------------------
    # SEARCH METHODS
    # ------------------------------------------------------------

    def _search_contract_renewal_due_soon(self, operator, value):
        params = self.env["ir.config_parameter"].sudo()
        delay_alert_contract = int(
            params.get_param("hr_fleet.delay_alert_contract", default=30)
        )
        res = []
        assert operator in ("=", "!=", "<>") and value in (
            True,
            False,
        ), "Operation not supported"
        if (operator == "=" and value is True) or (
            operator in ("<>", "!=") and value is False
        ):
            search_operator = "in"
        else:
            search_operator = "not in"
        today = fields.Date.context_today(self)
        datetime_today = fields.Datetime.from_string(today)
        limit_date = fields.Datetime.to_string(
            datetime_today + relativedelta(days=+delay_alert_contract)
        )
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies"
            )
        except ValueError:
            # During installation, return empty results
            return []
        res_ids = (
            self.env["product.asset.log"]
            .search(
                [
                    ("date_end", ">", today),
                    ("date_end", "<", limit_date),
                    ("product_category_id", "=", contract_category.id),
                    ("state", "in", ["open", "expired"]),
                ]
            )
            .mapped("asset_id")
            .ids
        )
        res.append(("id", search_operator, res_ids))
        return res

    def _search_get_overdue_contract_reminder(self, operator, value):
        res = []
        assert operator in ("=", "!=", "<>") and value in (
            True,
            False,
        ), "Operation not supported"
        if (operator == "=" and value is True) or (
            operator in ("<>", "!=") and value is False
        ):
            search_operator = "in"
        else:
            search_operator = "not in"
        today = fields.Date.context_today(self)
        # get the id of vehicles that have overdue contracts
        # but exclude those for which a new contract has already been created for them
        asset_ids = self.env["fleet.vehicle"]._search(
            [
                (
                    "contract_ids",
                    "any",
                    [
                        ("date_end", "!=", False),
                        ("date_end", "<", today),
                        ("state", "in", ["open", "expired"]),
                    ],
                ),
                "!",
                (
                    "contract_ids",
                    "any",
                    [
                        ("date_end", "!=", False),
                        ("date_end", ">=", today),
                        ("state", "in", ["open", "futur"]),
                    ],
                ),
            ]
        )
        res.append(("id", search_operator, asset_ids))
        return res

    # ------------------------------------------------------------
    # ACTION METHODS
    # ------------------------------------------------------------

    def action_view_logs_assignation(self):
        self.ensure_one()
        assignment_product_category = self.env.ref(
            "product_asset.product_category_maintenance_and_repairs"
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "product_asset.action_product_asset_log"
        )
        action["domain"] = [
            ("asset_id", "=", self.id),
            ("product_category_id", "=", assignment_product_category.id),
        ]
        action["context"] = {
            "default_asset_id": self.id,
            "default_operator_id": self.operator_id.id,
            "default_product_category_id": assignment_product_category.id,
        }
        return action

    def action_view_logs_cost(self):
        """
        This opens log view to view and add new log for this vehicle, groupby default to only show effective costs
        @return: the costs log view
        """
        self.ensure_one()
        service_categories = self.env.ref(
            "product_asset.product_category_fuel"
        ) + self.env.ref("product_asset.product_category_highway_toll")
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "product_asset.action_product_asset_log"
        )
        action["domain"] = [
            ("asset_id", "=", self.id),
            ("product_category_id", "in", service_categories.ids),
        ]
        action["context"] = {
            "default_asset_id": self.id,
            "search_default_parent_false": True,
            "search_default_groupby_product_category_id": True,
        }
        return action

    def action_view_context(self):
        """
        This opens the xml view specified in xml_id for the current vehicle (contracts)
        """
        self.ensure_one()
        contract_product_category = self.env.ref(
            "product_asset.product_category_insurance_and_policies"
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "product_asset.action_product_asset_log"
        )
        action["domain"] = [
            ("asset_id", "=", self.id),
            ("product_category_id", "=", contract_product_category.id),
        ]
        action["context"] = {
            "default_asset_id": self.id,
            "default_product_category_id": contract_product_category.id,
        }
        return action

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def accept_operator_change(self):
        # Find all the vehicles of the same type for which the driver is the future_operator_id
        # remove their operator_id and close their history using current date
        vehicles = self.search(
            [
                ("operator_id", "in", self.mapped("future_operator_id").ids),
                ("asset_type", "=", self.asset_type),
            ]
        )
        vehicles.write({"operator_id": False})
        for vehicle in self:
            vehicle.operator_id = vehicle.future_operator_id
            vehicle.future_operator_id = False

    def create_operator_assignment_log(self, vals):
        for vehicle in self:
            self.env["product.asset.log"].create(
                vehicle._prepare_operator_assignment_data(vals)
            )

    def _get_analytic_name(self):
        # This function is used in fleet_account and is overrided in l10n_be_hr_payroll_fleet
        return self.license_plate or _("No plate")

    def _get_product_contract(self):
        product = self.env.ref(
            "product_asset.product_product_insurance", raise_if_not_found=False
        )
        return product or self.env["product.product"]

    def _get_product_operator_assignment(self):
        product = self.env.ref(
            "product_asset.product_product_operator_assignment",
            raise_if_not_found=False,
        )
        return product or self.env["product.product"]

    def _prepare_operator_assignment_data(self, vals):
        self.ensure_one()
        assignment = self._get_product_operator_assignment()
        return {
            "asset_id": self.id,
            "operator_id": vals["operator_id"],
            "product_id": assignment.id or False,
            "date_start": fields.Date.today(),
            "odometer": self.odometer,
        }
