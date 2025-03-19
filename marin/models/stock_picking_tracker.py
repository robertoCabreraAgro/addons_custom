from odoo import api, fields, models
from odoo.exceptions import UserError


class StockPickingTracker(models.Model):
    _name = "stock.picking.tracker"
    _description = "Picking Route Tracker"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    # Main block
    name = fields.Char(
        string="Reference",
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: self.env._("New"),
    )
    allowed_picking_ids = fields.One2many(
        comodel_name="stock.picking",
        compute="_compute_allowed_picking_ids",
    )
    picking_ids = fields.One2many(
        comodel_name="stock.picking",
        inverse_name="tracker_id",
        string="Transfers",
        check_company=True,
        domain="[('id', 'in', allowed_picking_ids)]",
        help="List of transfers associated to this tracker",
    )
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Operation Type",
        required=True,
    )
    vehicle_id = fields.Many2one(
        comodel_name="fleet.vehicle",
        string="Vehicle",
        tracking=True,
    )
    driver_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Driver",
        compute="_compute_driver_id",
        store=True,
        readonly=False,
    )
    driver_department_id = fields.Many2one(
        "hr.department",
        compute="_compute_driver_department_id",
        store=True,
        compute_sudo=True,
    )
    driver_is_commercial = fields.Boolean(compute="_compute_driver_is_commercial")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        copy=False,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        tracking=True,
        default=lambda self: self.env.user,
        check_company=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    scheduled_date = fields.Datetime(copy=False)
    note = fields.Text("Internal Note")

    # Date and time block
    date_start = fields.Datetime(string="Route Start")
    date_end = fields.Datetime(string="Route End")

    # Odometer block
    odometer_start = fields.Float(string="Starting Odometer")
    odometer_end = fields.Float(string="Ending Odometer")
    odometer_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Odometer Unit",
        related="vehicle_id.odometer_uom_id",
        readonly=True,
        store=True,
        help="Unit of measurement for the odometer, coming from the vehicle.",
    )
    odometer_difference = fields.Float(
        string="Distance Traveled",
        compute="_compute_odometer_difference",
        store=True,
        help="Difference between end and start odometer values.",
    )

    # Fuel block
    fuel_start = fields.Float(
        string="Starting Fuel",
        help="Percentage (%) of fuel level at the beginning of the route",
    )
    fuel_end = fields.Float(
        string="Ending Fuel",
        help="Percentage (%) of fuel level at the end of the route",
    )
    fuel_uom_id = fields.Many2one(
        "uom.uom",
        string="Fuel Unit",
        readonly=True,
        default=lambda self: self.env.ref("uom.product_uom_litre"),
        help="Unit of measurement for fuel, coming from the vehicle.",
    )
    fuel_consumption = fields.Float(
        compute="_compute_fuel_consumption",
        store=True,
        help="Since each vehicle has a different fuel tank capacity, a rule of three "
        "is applied to convert the consumed fuel into liters or the default volume unit "
        "defined in the global parameters.",
    )

    # Empty block
    empty_distance = fields.Float(
        string="Empty Distance Traveled",
        compute="_compute_empty_distance",
        store=True,
        help="Distance traveled without carrying goods",
    )
    empty_fuel = fields.Float(
        string="Empty Fuel Consumption",
        compute="_compute_empty_fuel",
        store=True,
        help="Fuel consumed while traveling without goods",
    )

    # Efficiency block
    fuel_efficiency = fields.Float(
        compute="_compute_fuel_efficiency",
        store=True,
        help="Fuel efficiency calculated as distance per fuel unit.",
    )
    fuel_efficiency_uom_id = fields.Many2one(
        "uom.uom",
        string="Fuel Efficiency Unit",
        readonly=True,
    )

    @api.depends("company_id", "picking_type_id", "state")
    def _compute_allowed_picking_ids(self):
        allowed_picking_states = ["waiting", "confirmed", "assigned"]
        for tracker in self:
            domain_states = list(allowed_picking_states)
            # Allows to add draft pickings only if tracker is in draft as well.
            if tracker.state == "draft":
                domain_states.append("draft")
            domain = [
                ("company_id", "=", tracker.company_id.id),
                ("state", "in", domain_states),
            ]
            if tracker.picking_type_id:
                domain += [("picking_type_id", "=", tracker.picking_type_id.id)]
            tracker.allowed_picking_ids = self.env["stock.picking"].search(domain)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", self.env._("New")) == self.env._("New"):
                company_id = vals.get("company_id", self.env.company.id)
                vals["name"] = self.env["ir.sequence"].with_company(
                    company_id
                ).next_by_code("stock.picking.tracker") or self.env._("New")
        return super().create(vals_list)

    @api.depends("vehicle_id")
    def _compute_driver_id(self):
        for tracker in self:
            tracker.driver_id = tracker.vehicle_id.driver_id

    @api.depends("driver_id")
    def _compute_driver_department_id(self):
        for tracker in self:
            tracker.driver_department_id = tracker.driver_id.department_id

    def _compute_driver_is_commercial(self):
        commercial_department = self.sudo().env.ref("marin_data.hr_department_4")
        for tracker in self:
            driver_is_commercial = False
            if tracker.driver_department_id and commercial_department:
                driver_is_commercial = (
                    tracker.driver_department_id == commercial_department
                )
            tracker.driver_is_commercial = driver_is_commercial

    @api.depends("odometer_start", "odometer_end")
    def _compute_odometer_difference(self):
        """Compute the difference between the starting and ending odometer readings."""
        for tracker in self:
            if tracker.odometer_start and tracker.odometer_end:
                tracker.odometer_difference = (
                    tracker.odometer_end - tracker.odometer_start
                )
            else:
                tracker.odometer_difference = 0.0

    @api.depends("fuel_start", "fuel_end", "vehicle_id.fuel_tank_capacity")
    def _compute_fuel_consumption(self):
        """Compute the fuel consumption."""
        for tracker in self:
            if (
                tracker.fuel_start
                and tracker.fuel_end
                and tracker.vehicle_id.fuel_tank_capacity
            ):
                # Convert percentage to actual fuel quantity
                start_fuel = tracker.vehicle_id.fuel_tank_capacity * (
                    tracker.fuel_start / 100
                )
                end_fuel = tracker.vehicle_id.fuel_tank_capacity * (
                    tracker.fuel_end / 100
                )
                tracker.fuel_consumption = start_fuel - end_fuel
            else:
                tracker.fuel_consumption = 0.0

    @api.depends("odometer_end", "picking_ids.odometer_done")
    def _compute_empty_distance(self):
        """Compute the empty distance."""
        for tracker in self:
            tracker_pickings = tracker.picking_ids
            empty_distance = 0
            if all(p.state in ["done", "cancel"] for p in tracker_pickings):
                # Get the last delivered picking
                last_picking = tracker_pickings.filtered(
                    lambda p: p.state == "done"
                ).sorted(key=lambda p: p.date_done, reverse=True)[:1]
                empty_distance = (
                    tracker.odometer_end - last_picking.odometer_done
                    if last_picking
                    else 0
                )
            tracker.empty_distance = empty_distance

    @api.depends("fuel_end", "picking_ids.fuel_done")
    def _compute_empty_fuel(self):
        """Compute the empty fuel consumption."""
        for tracker in self:
            tracker_pickings = tracker.picking_ids
            empty_fuel = 0
            if all(p.state in ["done", "cancel"] for p in tracker_pickings):
                # Get the last delivered picking
                last_picking = tracker_pickings.filtered(lambda p: p.fuel_done).sorted(
                    "date_done"
                )[-1:]
                empty_fuel = (
                    tracker.fuel_end - last_picking.fuel_done if last_picking else 0
                )
            tracker.empty_fuel = empty_fuel

    @api.depends("odometer_difference", "fuel_consumption")
    def _compute_fuel_efficiency(self):
        """Compute the fuel efficiency."""
        for tracker in self:
            if tracker.odometer_difference and tracker.fuel_consumption > 0:
                tracker.fuel_efficiency = (
                    tracker.odometer_difference / tracker.fuel_consumption
                )
            else:
                tracker.fuel_efficiency = 0.0

    def action_confirm(self):
        """Confirm the tracker and set it to in_progress"""
        self.ensure_one()

        if not self.picking_ids:
            raise UserError(
                self.env._("You have to set some pickings to this tracker.")
            )

        # Check odometer and fuel values
        if not self.odometer_start:
            raise UserError(
                self.env._(
                    "You cannot confirm this tracker because the starting odometer value is not set."
                )
            )

        if not self.fuel_start:
            raise UserError(
                self.env._(
                    "You cannot confirm this tracker because the starting fuel value is not set."
                )
            )

        self.picking_ids.action_confirm()
        self._check_company()

        return self.write(
            {
                "state": "in_progress",
                "date_start": self.date_start or fields.Datetime.now(),
            }
        )

    def action_done(self):
        """Mark the tracker as done after validating ending values"""
        self.ensure_one()

        # Check tracker requirements
        if not self.odometer_end:
            raise UserError(
                self.env._(
                    "You cannot mark as done this tracker because the ending odometer value is not set."
                )
            )

        if not self.fuel_end:
            raise UserError(
                self.env._(
                    "You cannot mark as done this tracker because the ending fuel value is not set."
                )
            )

        # Check picking requirements
        pickings_not_done = []
        pickings_without_odometer = []
        pickings_without_fuel = []
        all_pickings_cancelled = True

        for picking in self.picking_ids:  # pylint: disable=not-an-iterable
            if picking.state not in ["done", "cancel"]:
                pickings_not_done.append(picking.name)
            elif picking.state == "done":
                if not picking.odometer_done:
                    pickings_without_odometer.append(picking.name)
                if not picking.fuel_done:
                    pickings_without_fuel.append(picking.name)
                if all_pickings_cancelled:
                    all_pickings_cancelled = False

        if pickings_not_done:
            raise UserError(
                self.env._(
                    "You cannot mark as done this tracker because the following pickings are not done or cancelled: %s",
                    ", ".join(pickings_not_done),
                )
            )

        if pickings_without_odometer:
            raise UserError(
                self.env._(
                    "Cannot mark as done because the following pickings don't have odometer values: %s",
                    ", ".join(pickings_without_odometer),
                )
            )

        if pickings_without_fuel:
            raise UserError(
                self.env._(
                    "Cannot mark as done because the following pickings don't have fuel values: %s",
                    ", ".join(pickings_without_fuel),
                )
            )

        if all_pickings_cancelled:
            raise UserError(
                self.env._(
                    "You cannot mark as done this tracker because all pickings are cancelled"
                )
            )

        return self.write(
            {
                "state": "done",
                "date_end": self.date_end or fields.Datetime.now(),
            }
        )

    def action_cancel(self):
        """Cancel the tracker"""
        self.state = "cancel"
        self.picking_ids = False
        return True

    def action_draft(self):
        """Reset the tracker to draft"""
        return self.write({"state": "draft"})

    def action_update_odometer_start(self):
        """Action to get odometer from GPS at start a route"""
        self.ensure_one()
        self.odometer_start = self.vehicle_id._get_gps_odometer()

    def action_update_fuel_start(self):
        """Action to get fuel level from GPS at start a route"""
        self.ensure_one()
        self.fuel_start = self.vehicle_id._get_gps_fuel_level()

    def action_update_odometer_end(self):
        """Action to get odometer from GPS at end a route"""
        self.ensure_one()
        self.odometer_end = self.vehicle_id._get_gps_odometer()

    def action_update_fuel_end(self):
        """Action to get fuel level from GPS at end a route"""
        self.ensure_one()
        self.fuel_end = self.vehicle_id._get_gps_fuel_level()

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        pickings = self.picking_ids
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        action["context"] = dict(self._context, create=False, edit=False)
        return action
