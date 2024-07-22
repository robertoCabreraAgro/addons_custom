from odoo import api, fields, models


class StockScrapInherit(models.Model):
    _inherit = "stock.scrap"

    lot_id = fields.Many2one(domain="lot_domain")
    lot_domain = fields.Binary("Lot domain", compute="_compute_lot_domain")

    @api.depends("company_id", "location_id", "product_id")
    def _compute_lot_domain(self):
        for scrap in self:
            quant_lot_ids = scrap.location_id.quant_ids.filtered(
                lambda q: q.quantity > 0 and q.company_id == scrap.company_id
            ).mapped("lot_id")
            scrap.lot_domain = [
                ("company_id", "=", scrap.company_id.id),
                ("product_id", "=", scrap.product_id.id),
                ("id", "in", quant_lot_ids.ids),
            ]
