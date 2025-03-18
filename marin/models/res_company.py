from odoo import api, fields, models
from odoo.osv import expression


class ResCompany(models.Model):
    _inherit = "res.company"

    code = fields.Char(string="Short Code", size=6)
    complete_name = fields.Char(compute="_compute_complete_name", store=True)

    _code_uniq = models.Constraint("UNIQUE(code)", "The company's code must be unique")

    @api.depends("code", "name")
    def _compute_complete_name(self):
        for company in self:
            if not company.code:
                company.complete_name = company.name
            else:
                company.complete_name = f"{company.code} - {company.name}"

    # @api.model
    # def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
    #     domain = domain or []
    #     if name:
    #         name_domain = ["|", ("code", operator, name), ("name", operator, name)]
    #         return self._search(expression.AND([name_domain, domain]), limit=limit, order=order)
    #     return super()._name_search(name, domain, operator, limit, order)
