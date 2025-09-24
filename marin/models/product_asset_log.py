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
            "name": "Importar Logs",
            "type": "ir.actions.act_window",
            "res_model": "product.asset.log.import",
            "view_mode": "form",
            "target": "new",
        }
