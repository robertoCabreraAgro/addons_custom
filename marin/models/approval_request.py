from odoo import api, _, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context

class ApprovalRequest(models.Model):
    _inherit = "approval.request"


    has_vehicle = fields.Selection(
        related="category_id.has_vehicle", store=True,
    )
    has_odometer = fields.Selection(
        related="category_id.has_odometer", store=True,
    )
    vehicle_id = fields.Many2one(
        comodel_name="fleet.vehicle",
        string="Vehicle",
        compute="_compute_vehicle_id", store=True,
        readonly=False,
    )
    license_plate = fields.Char(
        string="License Plate",
        compute="_compute_vehicle_info", store=True,
    )
    fuel_type = fields.Char(
        string="Fuel Type",
        compute="_compute_vehicle_info", store=True,
    )
    odometer = fields.Integer(
        string="Odometer",
        help="Enter the vehicle's current odometer reading.",
    )
    log_ids = fields.One2many(
        comodel_name="fleet.vehicle.log",
        inverse_name="approval_request_id",
        string="Log",
    )


    @api.depends("request_owner_id")
    def _compute_vehicle_id(self):
        for record in self:
            if record.request_owner_id:
                vehicle = self.env["fleet.vehicle"].search(
                    [("driver_id", "=", record.request_owner_id.partner_id.id)], limit=1
                )
                record.vehicle_id = vehicle if vehicle else False
            else:
                record.vehicle_id = False

    @api.depends("vehicle_id")
    def _compute_vehicle_info(self):
        for record in self:
            if record.vehicle_id:
                record.license_plate = record.vehicle_id.license_plate
                record.fuel_type = record.vehicle_id.fuel_type
            else:
                record.license_plate = False
                record.fuel_type = False

    def action_confirm(self):
        for request in self:
            if request.approval_type == 'fleet_vehicle_log' and not request.odometer:
                raise UserError(_("You cannot create a log without odometer value."))
        return super().action_confirm()

    def action_create_fleet_vehicle_log(self):
        self.ensure_one()
        self.env["fleet.vehicle.log"].create(
            {
                "approval_request_id": self.id,
                "vehicle_id": self.vehicle_id.id,
                "odometer": self.odometer,
                "state": "done",
                "date": self.date, #TODO ROberto implement logic for date when all approvers have finished
                # "product_id": self.product_line_ids[0].product_id.id,
            }
        )

    def action_open_fleet_vehicle_log(self):
        self.ensure_one()
        log_ids = self.log_ids.ids
        domain = [('id', 'in', log_ids)]
        action = {
            'name': _('Logss'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle.log',
            'view_type': 'list',
            'view_mode': 'list,form',
            'context': clean_context(self.env.context),
            'domain': domain,
        }
        return action
