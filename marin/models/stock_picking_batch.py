from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    # Date and time block
    date_start = fields.Datetime(string='Route Start')
    date_end = fields.Datetime(string='Route End')
    
    # Odometer block
    odometer_start = fields.Float(string='Starting Odometer')
    odometer_end = fields.Float(string='Ending Odometer')
    odometer_uom_id = fields.Many2one(
        'uom.uom',
        string='Odometer Unit',
        related='vehicle_id.odometer_uom_id',
        readonly=True,
        store=True,
        help="Unit of measurement for the odometer, coming from the company or vehicle.",
    )
    odometer_difference = fields.Float(
        string='Odometer Difference',
        compute='_compute_odometer_difference',
        store=True,
        help="Difference between end and start odometer values.",
    )
    
    # Fuel block
    fuel_start = fields.Float(
        string='Starting Fuel',
        help='Percentage (%) of fuel level at the beginning of the route',
    )
    fuel_end = fields.Float(
        string='Ending Fuel',
        help='Percentage (%) of fuel level at the end of the route',
    )
    fuel_uom_id = fields.Many2one(
        'uom.uom',
        string='Fuel Unit',
        readonly=True,
        default=lambda self: self.env.ref('uom.product_uom_litre'),
        help="Unit of measurement for fuel, coming from the company or vehicle."
    )
    fuel_consumption = fields.Float(
        string='Fuel Consumption',
        compute='_compute_fuel_consumption',
        store=True,
        help="Since each vehicle has a different fuel tank capacity, A rule of three "
        "is applied to convert the consumed fuel into liters or the default volume unit "
        "defined in the global parameters.",
    )
    # Empty block
    empty_distance = fields.Float(
        string='Empty Distance',
        compute="_compute_empty_distance",
        store=True,
        help='Distance traveled without carrying goods'
    )
    empty_fuel = fields.Float(
        string='Empty Fuel Consumption', 
        compute="_compute_empty_fuel",
        store=True, 
        help='Fuel consumed while traveling without goods'
    )
    
    # Efficiency block
    fuel_efficiency = fields.Float(
        string='Fuel Efficiency',
        compute='_compute_fuel_efficiency',
        store=True,
        help="Fuel efficiency calculated as distance per fuel unit."
        
    )
    fuel_efficiency_uom_id = fields.Many2one(
        'uom.uom',
        string='Fuel Efficiency Unit',
        default=lambda self: self.env.ref('marin.uom_km_per_liter'),
        readonly=True,
    )
    driver_department_id = fields.Many2one(
        'hr.department',
        compute='_compute_driver_department_id',
        store=True,
        compute_sudo=True,
    )
    driver_is_commercial = fields.Boolean(compute="_compute_driver_is_commercial")

    @api.depends('driver_id')
    def _compute_driver_department_id(self):
        for batch in self:
            batch.driver_department_id = batch.driver_id.department_id

    def _compute_driver_is_commercial(self):
        commercial_department = self.sudo().env.ref("marin_data.hr_department_4")
        for batch in self:
            driver_is_commercial = False
            if batch.driver_department_id and commercial_department:
                driver_is_commercial = batch.driver_department_id == commercial_department
            batch.driver_is_commercial = driver_is_commercial

    @api.depends('odometer_start', 'odometer_end')
    def _compute_odometer_difference(self):
        """Compute the difference between the starting and ending odometer readings.

        Calculates the difference between `odometer_end` and `odometer_start`
        and stores the result in `odometer_difference`. If either start or end
        odometer is not set, the difference is set to 0.0.
        """
        for batch in self:
            if batch.odometer_start and batch.odometer_end:
                batch.odometer_difference = batch.odometer_end - batch.odometer_start
            else:
                batch.odometer_difference = 0.0

    @api.depends('fuel_start', 'fuel_end')
    def _compute_fuel_difference(self):
        """Compute the difference between the starting and ending fuel levels.

        Calculates the difference between `fuel_start` and `fuel_end` and stores
        the result in `fuel_difference`. If either start or end fuel level is
        not set, the difference is set to 0.0.
        """
        for batch in self:
            if batch.fuel_start and batch.fuel_end:
                batch.fuel_difference = batch.fuel_start - batch.fuel_end
            else:
                batch.fuel_difference = 0.0

    @api.depends('odometer_end', 'picking_ids.odometer_done')
    def _compute_empty_distance(self):
        """Compute the empty distance.

        Calculates the distance traveled empty by subtracting the last recorded
        odometer value from the ending odometer value of the batch. If no odometer
        value is recorded for the last picking, the empty distance is set to 0.0.
        """
        for batch in self:
            batch_pickings = batch.picking_ids
            empty_distance = 0
            if all(p.state in ["done", "cancel"] for p in batch_pickings):
                # Get the last delivered picking
                last_picking = batch_pickings.filtered(lambda p: p.state == 'done').sorted(
                    key=lambda p: p.date_done, reverse=True)[:1]
                empty_distance = batch.odometer_end - last_picking.odometer_done if last_picking else 0
            batch.empty_distance = empty_distance

    @api.depends('fuel_end', 'picking_ids.fuel_done')
    def _compute_empty_fuel(self):
        """Compute the empty fuel consumption.

        Calculates the fuel consumed while the vehicle is empty, by subtracting the last
        recorded fuel level from the ending fuel level of the batch. If no fuel level
        is recorded for the last picking, the empty fuel consumption is set to 0.0.
        """
        for batch in self:
            batch_pickings = batch.picking_ids
            empty_fuel = 0
            if all(p.state in ["done", "cancel"] for p in batch_pickings):
                # Get the last delivered picking
                last_picking = batch_pickings.filtered(lambda p: p.fuel_done).sorted('date_done')[-1:]
                empty_fuel = batch.fuel_end - last_picking.fuel_done if last_picking else 0
            batch.empty_fuel = empty_fuel

    @api.depends('fuel_start', 'fuel_end', 'vehicle_id.fuel_tank_capacity')
    def _compute_fuel_consumption(self):
        """Compute the fuel consumption.

        Calculates the fuel consumption based on the starting and ending fuel levels
        and the vehicle's fuel tank capacity. The fuel levels are percentages, so they
        are converted to actual fuel quantities using the tank capacity. If any of
        the required fields are not set, the consumption is set to 0.0.
        """
        for batch in self:
            if batch.fuel_start and batch.fuel_end and batch.vehicle_id.fuel_tank_capacity:
                # Convert percentage to actual fuel quantity
                start_fuel = batch.vehicle_id.fuel_tank_capacity * (batch.fuel_start / 100)
                end_fuel = batch.vehicle_id.fuel_tank_capacity * (batch.fuel_end / 100)
                batch.fuel_consumption = start_fuel - end_fuel
            else:
                batch.fuel_consumption = 0.0

    @api.depends('odometer_difference', 'fuel_consumption')
    def _compute_fuel_efficiency(self):
        """Compute the fuel efficiency.

        Calculates the fuel efficiency by dividing the `odometer_difference`
        by the `fuel_consumption`. If either the odometer difference or fuel
        consumption is zero, or fuel consumption is negative, the efficiency
        is set to 0.0.
        """
        for batch in self:
            if batch.odometer_difference and batch.fuel_consumption > 0:
                batch.fuel_efficiency = batch.odometer_difference / batch.fuel_consumption
            else:
                batch.fuel_efficiency = 0.0

    def action_confirm(self):
        """Extend the action_confirm method to validate odometer and fuel before start route"""
        self.ensure_one()
        result = super(StockPickingBatch, self).action_confirm()

        # Record values at start
        odometer_start = self.odometer_start
        fuel_start = self.fuel_start

        # For commercial, we need to update odometer_end with the last picking odometer        
        if not odometer_start:
            raise UserError(_("You cannot mark as confirmed this batch because the starting odometer value is not set."))

        if not fuel_start:
            raise UserError(_("You cannot mark as confirmed this batch because the starting fuel value is not set."))

        return self.write({"date_start": self.date_start or fields.Datetime.now(), "odometer_end": odometer_end})

    def action_done(self):
        """Extend the action_done method to validate odometer and fuel before end route"""
        self.ensure_one()
        result = super(StockPickingBatch, self).action_done()

        # Record odometer at end
        odometer_end = self.odometer_end
        fuel_end = self.fuel_end

        # For commercial, we need to update odometer_end with the last picking odometer        
        if self.driver_is_commercial:
            odometer_end = self.vehicle_id._get_gps_odometer()

        if not odometer_end:
            raise UserError(_("You cannot mark as done this batch because the ending odometer value is not set."))

        if not fuel_end:
            raise UserError(_("You cannot mark as done this batch because the ending fuel value is not set."))
     
        return self.write({"date_end": self.date_end or fields.Datetime.now(), "odometer_end": odometer_end})

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
