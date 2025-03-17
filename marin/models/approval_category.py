from odoo import api, fields, models

from odoo.addons.approvals.models.approval_category import CATEGORY_SELECTION


class ApprovalCategory(models.Model):
    _inherit = "approval.category"


    # Inherited fields
    approval_type = fields.Selection(
        selection_add=[('fleet_vehicle_log', 'Create fleet log')]
    )

    # New fields
    has_vehicle = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Vehicle",
        required=True,
        default="no",
    )
    has_odometer = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="Has Odometer",
        required=True,
        default="no",
    )


    @api.onchange('approval_type')
    def _onchange_approval_type(self):
        if self.approval_type == 'fleet_vehicle_log':
            self.has_date = 'required'
            self.has_vehicle = 'required'
            self.has_odometer = 'required'
        else:
            super()._onchange_approval_type()
