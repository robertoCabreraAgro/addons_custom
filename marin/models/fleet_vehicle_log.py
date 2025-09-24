from odoo import fields, models


class FleetVehiclelog(models.Model):
    """Fleet Vehicle Log - Temporary model for migration"""

    _name = "fleet.vehicle.log"
    _description = "Fleet Vehicle Log"

    # Essential fields for fleet vehicle integration
    vehicle_id = fields.Many2one(
        comodel_name="fleet.vehicle",
        string="Vehicle",
        required=True,
        help="Vehicle associated with this log entry",
    )
    date = fields.Date(
        string="Date",
        default=fields.Date.today,
        help="Date of the log entry",
    )
    name = fields.Char(
        string="Description",
        help="Description of the log entry",
    )

    approval_request_id = fields.Many2one(
        comodel_name="approval.request",
    )
    qty_fuel = fields.Float(
        string="Fuel Quantity (Liters)",
        help="Quantity of fuel added to the vehicle",
    )
    efficiency = fields.Float(
        string="Efficiency (km/L)",
        aggregator="avg",
        help="Fuel efficiency in kilometers per liter",
    )
    vendor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
        domain=[("supplier", "=", True)],
        help="Service station or vendor where the fuel was purchased",
    )
    amount = fields.Monetary(
        string="Cost",
        help="Cost of the service or fuel purchase",
    )
    product_category_id = fields.Many2one(
        comodel_name="product.category",
        string="Product Category",
        help="Category of the product/service",
    )
    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("running", "Running"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Stage",
        default="new",
        help="Current status of the log entry",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    def action_open_upload_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Importar Logs",
            "res_model": "fleet.vehicle.log.import",
            "view_mode": "form",
            "target": "new",
        }
