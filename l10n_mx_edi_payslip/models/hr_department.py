from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    property_account_position_id = fields.Many2one(
        "account.fiscal.position",
        company_dependent=True,
        string="Fiscal Position",
        domain="[('company_id', '=', current_company_id)]",
        help="The fiscal position in departments determines the accounts used for journal items in the journal entries"
        " created by payroll. If the employee has a department, the journal items created by their salary concepts "
        "will have the account specified in department's fiscal position configuration.",
    )
