from odoo import api, fields, models


class HrPayslipExtra(models.Model):
    _name = "hr.payslip.extra"
    _description = "Allow define many extra inputs in the payslips"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True,
        tracking=True,
        help="Indicate the name for this record, could be taken from the document origin",
    )
    input_id = fields.Many2one(
        "hr.payslip.input.type",
        "Input to define in the payslips",
        tracking=True,
        required=True,
        help="This input will be set on the payslip inputs for the employees related.",
    )
    date = fields.Date(
        tracking=True,
        required=True,
        help="This extra will be paid on the payslip for this period",
    )
    detail_ids = fields.One2many(
        "hr.payslip.extra.detail",
        "extra_id",
        help="Indicate the employees to consider in this extra and the amount to each one.",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("approved", "Approved"),
        ],
        readonly=True,
        copy=False,
        default="draft",
        tracking=True,
        help="The extra must be approved to allow pay this on the employee payslips",
    )
    lines_count = fields.Integer(compute="_compute_lines_count")
    company_id = fields.Many2one(
        "res.company",
        readonly=True,
        default=lambda self: self.env.company,
    )

    @api.depends("detail_ids")
    def _compute_lines_count(self):
        for extra in self:
            extra.lines_count = len(extra.detail_ids)

    def action_approve(self):
        self.write({"state": "approved"})

    def action_cancel(self):
        self.write({"state": "draft"})

    def action_open_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip.extra.detail",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["id", "in", self.detail_ids.ids]],
            "name": "Lines",
        }
