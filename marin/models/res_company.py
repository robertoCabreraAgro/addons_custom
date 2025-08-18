from odoo import api, fields, models
from odoo.osv import expression


class ResCompany(models.Model):
    """Inherit ResCompany"""

    _inherit = "res.company"

    code = fields.Char(string="Short Code", size=6)
    complete_name = fields.Char(compute="_compute_complete_name", store=True)

    # Customer merge configuration
    customer_merge_required_fields = fields.Many2many(
        "ir.model.fields",
        string="Required Customer Fields",
        domain=[("model", "=", "res.partner")],
        help="Fields that must be completed to keep a customer active",
    )

    # Restricted contact creation configuration
    restricted_contact_required_fields = fields.Many2many(
        "ir.model.fields",
        "company_restricted_contact_fields_rel",
        "company_id",
        "field_id",
        string="Mandatory Contact Fields",
        domain=[("model", "=", "res.partner")],
        help="Fields that must be completed when restricted contact creation is enabled",
    )

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
