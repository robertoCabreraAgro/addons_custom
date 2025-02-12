from odoo import api, fields, models


class ApprovalRequest(models.Model):
    _inherit = "approval.request"
    
    has_vehicle = fields.Selection(
        related="category_id.has_vehicle", 
        store=True
    )
    has_license_plate = fields.Selection(
        related="category_id.has_license_plate", store=True
    )
    has_fuel_type = fields.Selection(
        related="category_id.has_fuel_type", 
        store=True
    )
    has_odometer = fields.Selection(
        related="category_id.has_odometer", 
        store=True
    )
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicle",
        compute="_compute_vehicle_id",
        store=True,
        readonly=False,
    )

    license_plate = fields.Char(
        string="License Plate", 
        compute="_compute_vehicle_info", 
        store=True
    )

    fuel_type = fields.Char(
        string="Fuel Type", 
        compute="_compute_vehicle_info", 
        store=True
    )

    odometer = fields.Float(
        string="Odometer", 
        help="Enter the vehicle's current odometer reading."
    )

    @api.depends("vehicle_id")
    def _compute_vehicle_info(self):
        for record in self:
            if record.vehicle_id:
                record.license_plate = record.vehicle_id.license_plate
                record.fuel_type = record.vehicle_id.fuel_type
            else:
                record.license_plate = False
                record.fuel_type = False

    @api.depends("request_owner_id")
    def _compute_vehicle_id(self):
        for record in self:
            if record.request_owner_id and record.request_owner_id.partner_id:
                vehicle = self.env["fleet.vehicle"].search(
                    [("driver_id", "=", record.request_owner_id.partner_id.id)], limit=1
                )
                record.vehicle_id = vehicle if vehicle else False
            else:
                record.vehicle_id = False
