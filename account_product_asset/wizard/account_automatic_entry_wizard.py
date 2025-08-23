from odoo import models


class AccountAutomaticEntryWizard(models.TransientModel):
    _inherit = "account.automatic.entry.wizard"

    def _get_move_line_dict_vals_change_period(self, aml, date):
        """Override to handle asset_id field in automatic entries."""
        res = super()._get_move_line_dict_vals_change_period(aml, date)
        if aml.asset_id:
            for move_line_data in res:
                if move_line_data[2]["account_id"] == aml.account_id.id:
                    move_line_data[2]["asset_id"] = aml.asset_id.id
        return res