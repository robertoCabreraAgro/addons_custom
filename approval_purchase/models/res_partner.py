from odoo import fields, models
from odoo.tools.translate import _


class ResPartner(models.Model):
    _inherit = "res.partner"

    category_id = fields.Many2many(
        default=lambda self: self._default_category(),
    )

    def _default_category(self):
        if self._context.get("unset_res_partner_category_id"):
            return False

        return super()._default_category()
