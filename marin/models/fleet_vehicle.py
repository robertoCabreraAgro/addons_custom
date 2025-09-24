from odoo import api, fields, models, Command
from odoo.tools.translate import _


class FleetVehicle(models.Model):
    """Inherit FleetVehicle"""

    _inherit = "fleet.vehicle"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    log_ids = fields.One2many(
        comodel_name="fleet.vehicle.log",
        inverse_name="vehicle_id",
        string="Vehicle Logs",
        help="All log entries for this vehicle",
    )
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
    )

    fuel_card_id = fields.Many2one(
        comodel_name="documents.document",
        store=True,
        readonly=False,
        inverse="_inverse_fuel_card_id",
        domain=lambda self: [
            ("tag_ids", "in", self.env.ref("marin.documents_fleet_fuel_card").ids),
        ],
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
    fuel_count = fields.Integer(
        string="Fuel",
        compute="_compute_fuel_count",
    )
    fuel_tank_capacity = fields.Float(
        string="Fuel Tank Capacity",
        default=0.0,
        help="Total fuel tank capacity in liters",
    )
    highway_pass_id = fields.Many2one(
        comodel_name="documents.document",
        store=True,
        readonly=False,
        inverse="_inverse_highway_pass_id",
        domain=lambda self: [
            (
                "tag_ids",
                "in",
                self.env.ref("marin.documents_fleet_highway_pass").ids,
            ),
        ],
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
        string="Highway Pass",
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

    def _compute_odometer(self):
        gps_vehicles = self.env["fleet.vehicle"]
        for vehicle in self:
            vehicle.odometer = vehicle.get_current_odometer()
            if vehicle.odometer:
                gps_vehicles |= vehicle
        return super(FleetVehicle, self - gps_vehicles)._compute_odometer()

    def _get_fuel_product_category(self):
        """Helper method to safely get fuel product category"""
        try:
            fuel_product_category = self.env.ref(
                "marin.product_category_fuel", raise_if_not_found=False
            )
        except:
            fuel_product_category = None

        if not fuel_product_category:
            # Fallback: search for fuel category by name
            fuel_product_category = self.env["product.category"].search(
                [("name", "=", "Fuels")], limit=1
            )

        return fuel_product_category

    def _get_highway_product_category(self):
        """Helper method to safely get highway toll product category"""
        try:
            highway_product_category = self.env.ref(
                "marin.product_category_highway_toll", raise_if_not_found=False
            )
        except:
            highway_product_category = None

        if not highway_product_category:
            # Fallback: search for highway category by name
            highway_product_category = self.env["product.category"].search(
                [("name", "=", "Highways")], limit=1
            )

        return highway_product_category

    def _compute_fuel_count(self):
        fuel_product_category = self._get_fuel_product_category()
        for vehicle in self:
            if fuel_product_category:
                vehicle.fuel_count = len(
                    vehicle.log_ids.filtered(
                        lambda l: l.product_category_id == fuel_product_category
                    )
                )
            else:
                vehicle.fuel_count = 0

    def _compute_highway_pass_count(self):
        highway_pass_product_category = self._get_highway_product_category()
        for vehicle in self:
            if highway_pass_product_category:
                vehicle.highway_pass_count = len(
                    vehicle.log_ids.filtered(
                        lambda l: l.product_category_id == highway_pass_product_category
                    )
                )
            else:
                vehicle.highway_pass_count = 0

    # Extend original method
    @api.depends(
        "model_id.brand_id.name",
        "model_id.name",
        "model_year",
        "color",
        "license_plate",
    )
    def _compute_vehicle_name(self):
        for vehicle in self:
            vehicle.name = "%s/%s %s/%s/%s" % (
                vehicle.model_id.brand_id.name or "",
                vehicle.model_id.name or "",
                vehicle.model_year or "",
                vehicle.color or "",
                vehicle.license_plate or _("No Plate"),
            )

    @api.depends("fuel_card_id")
    def _compute_fuel_card_name(self):
        for vehicle in self:
            name = ""
            if vehicle.fuel_card_id:
                name = vehicle.fuel_card_id.name.split(".", 1)[0]
                name = name.replace("Efecticard ", "")
            vehicle.fuel_card_name = name

    @api.depends("highway_pass_id")
    def _compute_highway_pass_name(self):
        for vehicle in self:
            name = ""
            if vehicle.highway_pass_id:
                name = vehicle.highway_pass_id.name.split(".", 1)[0]
                name = name.replace("IMDM ", "")
            vehicle.highway_pass_name = name

    @api.depends("log_ids.amount", "log_ids.state")
    def _compute_fuel_card_balance(self):
        """Calculates the current balance based on fuel credit/debit records"""
        fuel_product_category = self._get_fuel_product_category()
        for vehicle in self:
            if fuel_product_category:
                # Find all fuel log records associated with this vehicle (only done state)
                fuel_logs = self.env["fleet.vehicle.log"].search(
                    [
                        ("vehicle_id", "=", vehicle.id),
                        ("product_category_id", "=", fuel_product_category.id),
                        ("state", "=", "done"),
                    ]
                )
            else:
                fuel_logs = self.env["fleet.vehicle.log"]

            # Sum all movements (positive credits, negative debits)
            vehicle.fuel_card_balance = (
                vehicle.fuel_card_openning_balance
                + sum(fuel_logs.mapped("amount")) * -1
            )  # logs are considered cost of the vehicle, the balance in favor is negative

    @api.depends("log_ids.amount")
    def _compute_highway_pass_balance(self):
        """Compute current balance based on toll debit/credit records"""
        highway_pass_product_category = self._get_highway_product_category()
        for vehicle in self:
            if highway_pass_product_category:
                # Find all toll records associated with this vehicle
                highway_logs = self.env["fleet.vehicle.log"].search(
                    [
                        ("vehicle_id", "=", vehicle.id),
                        ("product_category_id", "=", highway_pass_product_category.id),
                    ]
                )
            else:
                highway_logs = self.env["fleet.vehicle.log"]

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
                0, vehicle.fuel_card_budget - vehicle.fuel_card_balance
            )

    @api.depends("highway_pass_budget", "highway_pass_balance")
    def _compute_highway_pass_balance_to_reload(self):
        """Compute the balance that needs to be reloaded based on monthly budget and current balance"""
        for vehicle in self:
            vehicle.highway_pass_balance_to_reload = max(
                0, vehicle.highway_pass_budget - vehicle.highway_pass_balance
            )

    # ------------------------------------------------------------
    # INVERSE METHODS
    # ------------------------------------------------------------

    def _inverse_fuel_card_id(self):
        """
        Set the vehicle on the corresponding document, and unset the vehicle on
        previously related documents
        """
        tag = self.env.ref("marin.documents_fleet_fuel_card", False)
        for vehicle in self:
            doc = vehicle.fuel_card_id
            other_docs = (
                doc.search(
                    [("vehicle_id", "=", vehicle.id), ("tag_ids", "in", tag.ids)]
                )
                - doc
            )
            if doc:
                doc.sudo().write(
                    {
                        "res_model": vehicle._name,
                        "res_id": vehicle.id,
                        "is_editable_attachment": True,
                        "vehicle_id": vehicle.id,
                    }
                )
            for od in other_docs:
                od.sudo().write(
                    {
                        "res_model": od._name,
                        "res_id": od.id,
                        "vehicle_id": False,
                    }
                )

    def _inverse_highway_pass_id(self):
        """
        Set the vehicle on the corresponding document, and unset the vehicle on
        previously related documents
        """
        tag = self.env.ref("marin.documents_fleet_highway_pass", False)
        for vehicle in self:
            doc = vehicle.highway_pass_id
            other_docs = (
                doc.search(
                    [("vehicle_id", "=", vehicle.id), ("tag_ids", "in", tag.ids)]
                )
                - doc
            )
            if doc:
                doc.sudo().write(
                    {
                        "res_model": vehicle._name,
                        "res_id": vehicle.id,
                        "is_editable_attachment": True,
                        "vehicle_id": vehicle.id,
                    }
                )
            for od in other_docs:
                od.sudo().write(
                    {
                        "res_model": od._name,
                        "res_id": od.id,
                        "vehicle_id": False,
                    }
                )

    # ------------------------------------------------------------
    #  ACTIONS
    # ------------------------------------------------------------

    def action_view_fuel_logs(self):
        self.ensure_one()
        fuel_product_category = self._get_fuel_product_category()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "fleet.action_fleet_vehicle_log"
        )
        if fuel_product_category:
            action["domain"] = [
                ("vehicle_id", "=", self.id),
                ("product_category_id", "=", fuel_product_category.id),
            ]
        else:
            action["domain"] = [
                ("id", "=", False)
            ]  # Empty domain if category not found
        action["context"] = {
            "default_vehicle_id": self.id,
            "default_product_category_id": (
                fuel_product_category.id if fuel_product_category else False
            ),
            "hide_product_category": True,
            "show_vendor": True,
            "search_default_groupby_product_category_id": False,
        }
        return action

    def action_view_highway_pass_logs(self):
        self.ensure_one()
        highway_pass_product_category = self._get_highway_product_category()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "fleet.action_fleet_vehicle_log"
        )
        if highway_pass_product_category:
            action["domain"] = [
                ("vehicle_id", "=", self.id),
                ("product_category_id", "=", highway_pass_product_category.id),
            ]
        else:
            action["domain"] = [
                ("id", "=", False)
            ]  # Empty domain if category not found
        action["context"] = {
            "default_vehicle_id": self.id,
            "default_product_category_id": (
                highway_pass_product_category.id
                if highway_pass_product_category
                else False
            ),
            "hide_product_category": True,
            "show_vendor": True,
            "search_default_groupby_product_category_id": False,
        }
        return action

    def _compute_move_ids(self):
        """Override the method to include fleet managers in addition to account readonly users.
        Allow fleet managers to see account move lines related to their vehicles.
        """
        has_account_readonly = self.env.user.has_group("account.group_account_readonly")
        has_fleet_manager = self.env.user.has_group("fleet.fleet_group_manager")

        if not (has_account_readonly or has_fleet_manager):
            self.account_move_ids = False
            self.bill_count = 0
            return

        moves = self.env["account.move.line"]._read_group(
            domain=[
                ("vehicle_id", "in", self.ids),
                ("parent_state", "!=", "cancel"),
                (
                    "move_id.move_type",
                    "in",
                    self.env["account.move"].get_purchase_types(),
                ),
            ],
            groupby=["vehicle_id"],
            aggregates=["move_id:array_agg"],
        )
        vehicle_move_mapping = {
            vehicle.id: set(move_ids) for vehicle, move_ids in moves
        }
        for vehicle in self:
            vehicle.account_move_ids = [
                Command.set(vehicle_move_mapping.get(vehicle.id, []))
            ]
            vehicle.bill_count = len(vehicle.account_move_ids)
