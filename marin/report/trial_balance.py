from odoo import models


class TrialBalanceCustomHandler(models.AbstractModel):
    _inherit = "consolidation.trial.balance.report.handler"

    def _get_journal_col(self, journal, options):
        res = super()._get_journal_col(journal, options)
        cp = journal.company_period_id
        if cp and cp.company_name == res.get("name") and cp.company_code:
            res["name"] = cp.company_code
        return res
