from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    code = fields.Char(string="Short Code", size=6)
    complete_name = fields.Char(compute="_compute_complete_name", store=True)
    account_use_debit_limit = fields.Boolean(
        string="Purchase Debit Limit", help="Enable the use of debit limit on partners."
    )
    pos_cash_transfer_journal_id = fields.Many2one(
        "account.journal",
        string="PoS Cash Transfer Journal",
        domain=[("type", "in", ["cash", "bank"])],
        help="Accounting journal used to create pos cash withdraw.",
    )

    _sql_constraints = [("code_uniq", "unique (code)", "The company code must be unique !")]

    @api.depends("code", "name")
    def _compute_complete_name(self):
        for company in self:
            if not company.code:
                company.complete_name = company.name
            else:
                company.complete_name = "{} - {}".format(company.code, company.name)

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        args = args or []
        domain = []
        if name:
            domain = ["|", ("code", operator, name), ("name", operator, name)]
        company = self.search(domain + args, limit=limit)
        return company.name_get()
