from odoo import fields, models


class ProductAssetLog(models.Model):
    """Extend product.asset.log with fleet vehicle log functionality"""

    _inherit = "product.asset.log"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    approval_request_id = fields.Many2one(
        comodel_name="approval.request",
    )

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_open_upload_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Importar Logs",
            "res_model": "product.asset.log.import",
            "view_mode": "form",
            "target": "new",
        }
