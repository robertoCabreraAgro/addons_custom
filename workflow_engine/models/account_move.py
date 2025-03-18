from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        operation_line_obj = self.env["account.move.operation.line"]
        res = super().action_post()
        for move in self.filtered(lambda am: am.state == "posted"):
            line = operation_line_obj.search(
                [
                    ("action", "=", "move"),
                    ("state", "=", "in_progress"),
                    ("move_id", "=", move.id),
                ],
                limit=1,
            )
            if line:
                line.action_done()
        return res
