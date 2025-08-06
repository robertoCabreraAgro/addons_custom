from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.addons.product_asset.models.product_model import FUEL_TYPES


# Some fields don"t have the exact same name
MODEL_FIELDS_TO_VEHICLE = {
    "manufacturer_id": "manufacturer_id",
    "cilinders": "cilinders",
    "color": "color",
    "co2": "co2",
    "co2_standard": "co2_standard",
    "doors": "doors",
    "fuel_efficiency": "fuel_efficiency",
    "fuel_tank_capacity": "fuel_tank_capacity",
    "fuel_type": "fuel_type",
    "horsepower": "horsepower",
    "horsepower_tax": "horsepower_tax",
    "model_year": "model_year",
    "power": "power",
    "power_unit": "power_unit",
    "seats": "seats",
    "trailer_hook": "trailer_hook",
    "transmission": "transmission",
    "vehicle_range": "vehicle_range",
}


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    fleet_manager_id = fields.Many2one(
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
        help="Driver address of the vehicle",
    )
    mobility_card = fields.Char(
        # related="operator_id.mobility_card",
        # store=True,
    )
    future_operator_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Future Driver",
        domain='[("company_id", "in", (company_id, False))]',
        tracking=True,
        copy=False,
        help="Next Driver Address of the vehicle",
    )
    asset_type = fields.Selection(
        selection=[
            ("machinery", "Machinery"),
            ("product", "Product"),
            ("property", "Property"),
            ("vehicle", "Vehicle"),
        ],
        compute="_compute_model_fields",
        store=True,
        readonly=False,
    )
    location = fields.Char(
        help="Location of the vehicle (garage, ...)",
    )

    # Technical fields
    model_id = fields.Many2one(
        comodel_name="product.model",
        string="Model",
        tracking=True,
    )
    image_128 = fields.Image(
        compute="_compute_image_128",
        readonly=True,
    )
    manufacturer_id = fields.Many2one(
        compute="_compute_model_fields",
        store=True,
        readonly=False,
    )
    transmission = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("automatic", "Automatic"),
        ],
        string="Transmission",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
    )
    fuel_type = fields.Selection(
        FUEL_TYPES,
        string="Fuel Type",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
    )
    service_activity = fields.Selection(
        selection=[
            ("none", "None"),
            ("overdue", "Overdue"),
            ("today", "Today"),
        ],
        compute="_compute_service_activity",
    )
    # TODO make power unit a many2one
    power_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Power Unit",
        # default=lambda self: self.env.ref("uom.product_uom_km").id,
        # TODO implement domain for new uom logic
        # domain=lambda self: [
        #     ("model_category_id", "=", self.env.ref("uom.uom_categ_length").id),
        # ],
        copy=True,
        help="Odometer measure of the vehicle",
    )
    power_unit = fields.Selection(
        selection=[
            ("power", "kW"),
            ("horsepower", "Horsepower"),
        ],
        string="Power Unit",
        default="power",
    )
    power = fields.Integer(
        string="Power",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
        help="Power in kW of the vehicle",
    )
    odometer_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Odometer Unit",
        default=lambda self: self.env.ref("uom.product_uom_km").id,
        # TODO implement domain for new uom logic
        # domain=lambda self: [
        #     ("model_category_id", "=", self.env.ref("uom.uom_categ_length").id),
        # ],
        copy=True,
        help="Odometer unit of measure of the vehicle",
    )
    odometer = fields.Float(
        string="Odometer",
        compute="_compute_odometer",
        readonly=True,
        help="Odometer measure of the vehicle",
    )
    model_year = fields.Char(
        string="Model Year",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
        help="Year of the model",
    )
    # color_name = fields.Char(
    #     compute="_compute_model_fields",
    #     store=True,
    #     readonly=False,
    #     help="Color of the vehicle",
    # )
    doors = fields.Integer(
        string="Doors Number",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
        help="Number of doors of the vehicle",
    )
    seats = fields.Integer(
        string="Seats Number",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
        help="Number of seats of the vehicle",
    )
    fuel_tank_capacity = fields.Integer(
        string="Tank capacity",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
        help="Fuel tank capacity in liters",
    )
    cilinders = fields.Integer(
        string="Cilinders Number",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
    )
    co2 = fields.Float(
        string="CO2 Emissions",
        compute="_compute_model_fields",
        store=True,
        readonly=False,
        tracking=True,
        aggregator=None,
        help="CO2 emissions of the vehicle",
    )
    fuel_efficiency = fields.Float(
        compute="_compute_model_fields",
        store=True,
        readonly=False,
        aggregator="avg",
        help="Fuel efficiency in kilometers per liter (km/L)",
    )
    vehicle_range = fields.Float(string="Range")
    weight_capacity = fields.Float(
        string="Max Weight",
    )
    weight_capacity_uom_name = fields.Char(
        string="Weight unit of measure label",
        compute="_compute_weight_capacity_uom_name",
    )
    volume_capacity = fields.Float(
        string="Max Volume",
    )
    volume_capacity_uom_name = fields.Char(
        string="Volume unit of measure label",
        compute="_compute_volume_capacity_uom_name",
    )
    trailer_hook = fields.Boolean(
        string="Trailer Hitch",
        default=False,
        compute="_compute_model_fields",
        store=True,
        readonly=False,
    )

    # Identification fields
    license_plate = fields.Char(
        tracking=True,
        help="License plate number of the vehicle (i = plate number for a car)",
    )
    vin_sn = fields.Char(
        string="Chassis Number",
        copy=False,
        tracking=True,
        help="Unique number written on the vehicle chassis (VIN/SN number).",
    )
    engine_sn = fields.Char(
        string="Engine SN",
        tracking=True,
        help="Unique number written on the vehicle engine.",
    )
    vehicle_name = fields.Char(
        compute="_compute_vehicle_name",
        store=True,
    )

    # Financial fields
    date_acquisition = fields.Date(
        string="Registration Date",
        default=fields.Date.today,
        tracking=True,
        help="Date of vehicle registration",
    )
    date_write_off = fields.Date(
        string="Cancellation Date",
        tracking=True,
        help='Date when the vehicle"s license plate has been cancelled/removed.',
    )
    value_original = fields.Float(
        string="Catalog Value (VAT Incl.)",
        tracking=True,
    )
    value_residual = fields.Float()

    log_ids = fields.One2many(
        "product.asset.log",
        "vehicle_id",
        "Logs",
    )
    assignment_count = fields.Integer(
        string="Drivers History Count",
        compute="_compute_count_all",
    )
    service_count = fields.Integer(
        string="Services",
        compute="_compute_count_all",
    )
    contract_count = fields.Integer(
        string="Contracts",
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
    )
    contract_renewal_overdue = fields.Boolean(
        string="Has Contracts Overdue",
        compute="_compute_contract_reminder",
        search="_search_get_overdue_contract_reminder",
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
    )

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        ptc_values = [self._clean_vals_internal_user(vals) for vals in vals_list]
        vehicles = super().create(vals_list)
        for vehicle, vals, ptc_value in zip(vehicles, vals_list, ptc_values):
            if ptc_value:
                vehicle.sudo().write(ptc_value)
            if "operator_id" in vals and vals["operator_id"]:
                vehicle.create_driver_history(vals)
        return vehicles

    def write(self, vals):
        if "operator_id" in vals and vals["operator_id"]:
            operator_id = vals["operator_id"]
            for vehicle in self.filtered(lambda v: v.operator_id.id != operator_id):
                vehicle.create_driver_history(vals)

        if "active" in vals and not vals["active"]:
            self.env["product.asset.log"].search(
                [("vehicle_id", "in", self.ids)]
            ).active = False

        su_vals = self._clean_vals_internal_user(vals)
        if su_vals:
            self.sudo().write(su_vals)
        res = super().write(vals)
        return res

    def _track_subtype(self, init_values):
        self.ensure_one()
        if "operator_id" in init_values or "future_operator_id" in init_values:
            return self.env.ref("fleet.mt_fleet_driver_updated")

        return super()._track_subtype(init_values)

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_weight_capacity_uom_name(self):
        self.weight_capacity_uom_name = (
            self._get_weight_uom_name_from_ir_config_parameter()
        )

    def _compute_volume_capacity_uom_name(self):
        self.volume_capacity_uom_name = (
            self._get_volume_uom_name_from_ir_config_parameter()
        )

    def _compute_count_all(self):
        Log = self.env["product.asset.log"].with_context(active_test=False)
        contract_data = Log._read_group(
            [
                ("vehicle_id", "in", self.ids),
                ("type", "=", "contract"),
                ("state", "!=", "closed"),
            ],
            ["vehicle_id", "active"],
            ["__count"],
        )
        service_data = Log._read_group(
            [("vehicle_id", "in", self.ids), ("type", "=", "service")],
            ["vehicle_id", "active"],
            ["__count"],
        )
        history_data = Log._read_group(
            [("vehicle_id", "in", self.ids), ("type", "=", "driver")],
            ["vehicle_id"],
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
            vehicle.contract_count = mapped_contract_data[vehicle.id][vehicle.active]
            vehicle.service_count = mapped_service_data[vehicle.id][vehicle.active]
            vehicle.assignment_count = mapped_history_data[vehicle.id]

    @api.depends("model_id")
    def _compute_image_128(self):
        for product in self:
            if product.model_id:
                product.image_128 = product.manufacturer_id.image_128
            else:
                product.image_128 = product.image_1920

    @api.depends("model_id")
    def _compute_model_fields(self):
        """
        Copies all the related fields from the model to the vehicle
        """
        model_values = dict()
        for vehicle in self.filtered("model_id"):
            if vehicle.model_id.id in model_values:
                write_vals = model_values[vehicle.model_id.id]
            else:
                # copy if value is truthy
                write_vals = {
                    MODEL_FIELDS_TO_VEHICLE[key]: vehicle.model_id[key]
                    for key in MODEL_FIELDS_TO_VEHICLE
                    if vehicle.model_id[key]
                }
                model_values[vehicle.model_id.id] = write_vals
            vehicle.update(write_vals)

    @api.depends("manufacturer_id.name", "model_id.name", "license_plate")
    def _compute_vehicle_name(self):
        for vehicle in self:
            vehicle.vehicle_name = (
                (vehicle.model_id.manufacturer_id.name or "")
                + "/"
                + (vehicle.model_id.name or "")
                + "/"
                + (vehicle.license_plate or _("No Plate"))
            )
            # vehicle.name = f"{vehicle.model_id.manufacturer_id.name or ""}/{vehicle.model_id.name or ""}/{vehicle.license_plate or _("No Plate")}"

    @api.depends("log_ids")
    def _compute_service_activity(self):
        for vehicle in self:
            activities_state = set(
                state
                for state in vehicle.log_ids.mapped("activity_state")
                if state and state != "planned"
            )
            vehicle.service_activity = (
                sorted(activities_state)[0] if activities_state else "none"
            )

    @api.depends("log_ids")
    def _compute_contract_reminder(self):
        params = self.env["ir.config_parameter"].sudo()
        delay_alert_contract = int(
            params.get_param("hr_fleet.delay_alert_contract", default=30)
        )
        current_date = fields.Date.context_today(self)
        data = self.env["product.asset.log"]._read_group(
            domain=[
                ("date_end", "!=", False),
                ("vehicle_id", "in", self.ids),
                ("type", "=", "contract"),
                ("state", "!=", "closed"),
            ],
            groupby=["vehicle_id", "state"],
            aggregates=["date_end:max"],
        )
        prepared_data = {}
        for vehicle_id, state, date_end in data:
            if prepared_data.get(vehicle_id.id):
                if prepared_data[vehicle_id.id]["date_end"] < date_end:
                    prepared_data[vehicle_id.id]["date_end"] = date_end
                    prepared_data[vehicle_id.id]["state"] = state
            else:
                prepared_data[vehicle_id.id] = {
                    "state": state,
                    "date_end": date_end,
                }
        for vehicle in self:
            vehicle_data = prepared_data.get(vehicle.id)
            if vehicle_data:
                diff_time = (vehicle_data["date_end"] - current_date).days
                vehicle.contract_renewal_overdue = diff_time < 0
                vehicle.contract_renewal_due_soon = (
                    not vehicle.contract_renewal_overdue
                    and (diff_time < delay_alert_contract)
                )
                vehicle.contract_state = vehicle_data["state"]
            else:
                vehicle.contract_renewal_overdue = False
                vehicle.contract_renewal_due_soon = False
                vehicle.contract_state = ""

    @api.depends("log_ids", "log_ids.odometer")
    def _compute_odometer(self):
        for vehicle in self:
            if vehicle.log_ids:
                vehicle.odometer = max(vehicle.log_ids.mapped("odometer"))
            else:
                vehicle.odometer = 0.0

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
        res_ids = (
            self.env["product.asset.log"]
            .search(
                [
                    ("date_end", ">", today),
                    ("date_end", "<", limit_date),
                    ("type", "=", "contract"),
                    ("state", "in", ["open", "expired"]),
                ]
            )
            .mapped("vehicle_id")
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
        vehicle_ids = self.env["fleet.vehicle"]._search(
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
        res.append(("id", search_operator, vehicle_ids))
        return res

    # ------------------------------------------------------------
    # ACTION METHODS
    # ------------------------------------------------------------

    def action_view_assignation_logs(self):
        self.ensure_one()
        return {
            "name": _("Assignment Logs"),
            "type": "ir.actions.act_window",
            "res_model": "product.asset.log",
            "view_mode": "list",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {
                "default_operator_id": self.operator_id.id,
                "default_vehicle_id": self.id,
            },
        }

    def action_send_email(self):
        return {
            "name": _("Send Email"),
            "type": "ir.actions.act_window",
            "res_model": "fleet.vehicle.send.mail",
            "target": "new",
            "view_mode": "form",
            "context": {
                "default_vehicle_ids": self.ids,
            },
        }

    def action_view_bills(self):
        self.ensure_one()
        form_view_ref = self.env.ref("account.view_move_form", False)
        list_view_ref = self.env.ref("account_fleet.account_move_view_tree", False)
        result = self.env["ir.actions.act_window"]._for_xml_id(
            "account.action_move_in_invoice_type"
        )
        result.update(
            {
                "domain": [("id", "in", self.account_move_ids.ids)],
                "views": [(list_view_ref.id, "list"), (form_view_ref.id, "form")],
            }
        )
        return result

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def accept_driver_change(self):
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

    def act_show_log_cost(self):
        """
        This opens log view to view and add new log for this vehicle, groupby default to only show effective costs
        @return: the costs log view
        """
        self.ensure_one()
        copy_context = dict(self.env.context)
        copy_context.pop("group_by", None)
        res = self.env["ir.actions.act_window"]._for_xml_id(
            "fleet.fleet_vehicle_costs_action"
        )
        res.update(
            context=dict(
                copy_context,
                default_vehicle_id=self.id,
                search_default_parent_false=True,
            ),
            domain=[("vehicle_id", "=", self.id)],
        )
        return res

    def _clean_vals_internal_user(self, vals):
        # Fleet administrator may not have rights to write on partner
        # related fields when the operator_id is a res.user.
        # This trick is used to prevent access right error.
        su_vals = {}
        if self.env.su:
            return su_vals

        return su_vals

    def create_driver_history(self, vals):
        for vehicle in self:
            self.env["product.asset.log"].create(vehicle._get_driver_history_data(vals))

    def return_action_to_open(self):
        """
        This opens the xml view specified in xml_id for the current vehicle
        """
        self.ensure_one()
        xml_id = self.env.context.get("xml_id")
        if xml_id:
            res = self.env["ir.actions.act_window"]._for_xml_id(f"fleet.{xml_id}")
            res.update(
                context=dict(
                    self.env.context, default_vehicle_id=self.id, group_by=False
                ),
                domain=[("vehicle_id", "=", self.id)],
            )
            return res
        return False

    def _get_analytic_name(self):
        # This function is used in fleet_account and is overrided in l10n_be_hr_payroll_fleet
        return self.license_plate or _("No plate")

    def _get_driver_history_data(self, vals):
        self.ensure_one()
        return {
            "vehicle_id": self.id,
            "operator_id": vals["operator_id"],
            "type": "driver",
            "date_start": fields.Date.today(),
            "odometer": self.odometer,
        }
