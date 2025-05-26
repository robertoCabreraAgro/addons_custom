from odoo import api, fields, models
from odoo.tools.translate import _


class FleetVehicle(models.Model):
    """Inherit FleetVehicle"""

    _inherit = "fleet.vehicle"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

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
    fuel_count = fields.Integer(
        "Fuel",
        compute="_compute_fuel_count",
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

    def _compute_odometer(self):
        gps_vehicles = self.env["fleet.vehicle"]
        for vehicle in self:
            vehicle.odometer = vehicle._get_gps_odometer()
            if vehicle.odometer:
                gps_vehicles |= vehicle
        return super(FleetVehicle, self - gps_vehicles)._compute_odometer()

    def _compute_fuel_count(self):
        fuel_product_category = self.env.ref("marin.product_category_vehicle_fuel")
        for vehicle in self:
            vehicle.fuel_count = len(
                vehicle.log_ids.filtered(
                    lambda l: l.product_category_id == fuel_product_category
                )
            )

    def _compute_highway_pass_count(self):
        highway_pass_product_category = self.env.ref(
            "marin.product_category_vehicle_highway_pass"
        )
        for vehicle in self:
            vehicle.highway_pass_count = len(
                vehicle.log_ids.filtered(
                    lambda l: l.product_category_id == highway_pass_product_category
                )
            )

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

    @api.depends("log_ids.amount")
    def _compute_fuel_card_balance(self):
        """Calculates the current balance based on fuel credit/debit records"""
        fuel_product_category = self.env.ref("marin.product_category_vehicle_fuel")
        for vehicle in self:
            # Find all fuel log records associated with this vehicle
            fuel_logs = self.env["fleet.vehicle.log"].search(
                [
                    ("vehicle_id", "=", vehicle.id),
                    ("product_category_id", "=", fuel_product_category.id),
                ]
            )

            # Sum all movements (positive credits, negative debits)
            vehicle.fuel_card_balance = (
                vehicle.fuel_card_openning_balance
                + sum(fuel_logs.mapped("amount")) * -1
            )  # logs are considered cost of the vehicle, the balance in favor is negative

    @api.depends("log_ids.amount")
    def _compute_highway_pass_balance(self):
        """Compute current balance based on toll debit/credit records"""
        highway_pass_product_category = self.env.ref(
            "marin.product_category_vehicle_highway_pass"
        )
        for vehicle in self:
            # Find all toll records associated with this vehicle
            highway_logs = self.env["fleet.vehicle.log"].search(
                [
                    ("vehicle_id", "=", vehicle.id),
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
        tag = self.env.ref("marin_data.documents_fleet_fuel_card", False)
        for vehicle in self:
            doc = vehicle.fuel_card_id
            other_docs = (
                doc.search(
                    [("vehicle_id", "=", vehicle.id), ("tag_ids", "in", tag.ids)]
                )
                - doc
            )
            if doc:
                doc.write(
                    {
                        "res_model": vehicle._name,
                        "res_id": vehicle.id,
                        "is_editable_attachment": True,
                        "vehicle_id": vehicle.id,
                    }
                )
            for od in other_docs:
                od.write(
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
        tag = self.env.ref("marin_data.documents_fleet_highway_pass", False)
        for vehicle in self:
            doc = vehicle.highway_pass_id
            other_docs = (
                doc.search(
                    [("vehicle_id", "=", vehicle.id), ("tag_ids", "in", tag.ids)]
                )
                - doc
            )
            if doc:
                doc.write(
                    {
                        "res_model": vehicle._name,
                        "res_id": vehicle.id,
                        "is_editable_attachment": True,
                        "vehicle_id": vehicle.id,
                    }
                )
            for od in other_docs:
                od.write(
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
        fuel_product_category = self.env.ref("marin.product_category_vehicle_fuel")
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "fleet.action_fleet_vehicle_log"
        )
        action["domain"] = [
            ("vehicle_id", "=", self.id),
            ("product_category_id", "=", fuel_product_category.id),
        ]
        action["context"] = {
            "default_vehicle_id": self.id,
            "default_product_category_id": fuel_product_category.id,
            "hide_product_category": True,
            "show_vendor": True,
            "search_default_groupby_product_category_id": False,
        }
        return action

    def action_view_highway_pass_logs(self):
        self.ensure_one()
        highway_pass_product_category = self.env.ref(
            "marin.product_category_vehicle_highway_pass"
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "fleet.action_fleet_vehicle_log"
        )
        action["domain"] = [
            ("vehicle_id", "=", self.id),
            ("product_category_id", "=", highway_pass_product_category.id),
        ]
        action["context"] = {
            "default_vehicle_id": self.id,
            "default_product_category_id": highway_pass_product_category.id,
            "hide_product_category": True,
            "show_vendor": True,
            "search_default_groupby_product_category_id": False,
        }
        return action

    # ------------------------------------------------------------
    #  HELPERS
    # ------------------------------------------------------------

    def _get_gps_tracking_device(self, date=False):
        self.ensure_one()
        domain = [("vehicle_id", "=", self.id)]
        if date:
            domain += [("timestamp", "<", date)]
        return self.env["gps.tracking.device"].search(domain, order="id desc", limit=1)

    def _get_gps_odometer(self, date=False):
        """Get odometer reading from GPS"""
        self.ensure_one()
        gps_device = self._get_gps_tracking_device(date=date)
        return round(gps_device.last_point_id.odometer / 1000, 2)

    def _get_gps_fuel_level(self, date=False):
        """Get fuel level reading from GPS"""
        self.ensure_one()
        gps_device = self._get_gps_tracking_device(date=date)
        return round(gps_device.last_point_id.fuel_level, 2)
