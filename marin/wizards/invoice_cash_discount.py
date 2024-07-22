from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class AccountInvoiceCashDiscount(models.TransientModel):
    _name = "account.invoice.cash.discount"
    _description = "Compute cash discount directly on product unit price"

    move_ids = fields.Many2many("account.move", domain=[("state", "=", "posted")])
    amount = fields.Float(string="Percentage")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "move_ids" in fields_list and self._context.get("active_model") == "account.move" and "move_ids" not in res:
            moves = self.env["account.move"].browse(self._context.get("active_ids", []))
            if any(move.state != "posted" for move in moves):
                raise UserError(_("You can only register cash discounts on posted moves."))
            res["move_ids"] = [Command.set(moves.ids)]
        return res

    def action_invoice_cash_discount(self):
        for move in self.move_ids:
            move = move.with_context(check_move_validity=False)
            move.button_draft()
            for line in move.invoice_line_ids:
                if not line.product_id:
                    continue
                line.write({"price_unit": line.price_unit * (1 - (self.amount / 100.0))})
            move._post(soft=False)
