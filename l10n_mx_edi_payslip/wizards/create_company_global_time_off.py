from odoo import Command, fields, models


class CreateCompanyGlobalTimeOff(models.TransientModel):
    """This is a wizard class used to create a global time off. It was obtained from
    the odoo/enterprise module.
    Instead of adding the dependency, l10n_be_hr_payroll_posted_employee was ported,
    as this module depends on the  Belgian payroll, which could have issues with this
    module.
    """

    _name = "create.company.global.time.off"
    _description = "Create Company Public Time Off"

    name = fields.Char("Reason", required=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    date_from = fields.Datetime("Start Date", required=True)
    date_to = fields.Datetime("End Date", required=True)
    work_entry_type_id = fields.Many2one(
        "hr.work.entry.type",
        "Work Entry Type",
        required=True,
    )

    def action_confirm(self):
        self.ensure_one()
        self.env["resource.calendar"].search([("company_id", "=", self.company_id.id)]).write(
            {
                "leave_ids": [
                    Command.create(
                        {
                            "name": self.name,
                            "date_from": self.date_from,
                            "date_to": self.date_to,
                            "time_type": "leave",
                            "work_entry_type_id": self.work_entry_type_id.id,
                        },
                    )
                ]
            }
        )
