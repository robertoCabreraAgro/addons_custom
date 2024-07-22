from odoo import models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def _set_qty_producing(self):
        return super(MrpProduction, self.with_context(mrp_production=True))._set_qty_producing()
