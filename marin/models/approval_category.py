from odoo import fields, models
from odoo.addons.approvals.models.approval_category import CATEGORY_SELECTION



class ApprovalCategory(models.Model):
    _inherit = "approval.category"


    has_vehicle = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Vehicle",
        required=True,
    )
    has_license_plate = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has License Plate",
        required=True,
    )
    has_fuel_type = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Fuel Type",
        required=True,
    )
    has_odometer = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Odometer",
        required=True,
    )
