from odoo import models


class AccountMoveTemplate(models.Model):
    _inherit = "account.move.template"


    def generate_journal_entry(self):
        self.ensure_one()
        if self.move_type == "entry":
            return super().generate_journal_entry()
        wiz = self.env["account.invoice.template.run"].create({"template_id": self.id})
        wiz._onchange_template_id()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account_move_operation.account_invoice_template_run_action"
        )
        action.update({"res_id": wiz.id})
        return action
