from odoo import models


class StockQuant(models.Model):
    _inherit = "stock.quant"


    def action_stock_quant_relocate(self):
        res = super().action_stock_quant_relocate()
        view = self.env.ref('stock_move_location.stock_quant_relocate_form')
        res.update({"views": [(view.id, 'form')]})
        return res