from odoo import fields, models, _


CATEGORY_SELECTION = [
    ("required", "Required"),
    ("optional", "Optional"),
    ("no", "None"),
]


class ApprovalCategory(models.Model):
    _inherit = "approval.category"

    has_vehicle = fields.Selection(
        selection=CATEGORY_SELECTION, 
        string="Has Vehicle", 
        required=True
    )

    has_license_plate = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has License Plate",
        required=True,
    )

    has_odometer = fields.Selection(
        selection=CATEGORY_SELECTION, 
        string="Has Odometer", 
        required=True
    )

    has_fuel_type = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Fuel Type",
        required=True,
    )
