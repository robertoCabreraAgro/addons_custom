from odoo import api, fields, models


class HrPayslipInputBatch(models.Model):
    _name = "hr.payslip.input.batch"
    _description = "Allow define many extra inputs in the payslips"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True,
        help="Indicate the name for this record, could be taken from the document origin",
        tracking=True,
    )
    input_id = fields.Many2one(
        "hr.payslip.input.type",
        "Input to define in the payslips",
        help="This input will be set on the payslip inputs for the employees related.",
        tracking=True,
        required=True,
    )
    date = fields.Date(
        tracking=True,
        required=True,
        help="This extra will be paid on the payslip for this period",
    )
    detail_ids = fields.One2many(
        "hr.payslip.input.batch.detail",
        "extra_id",
        string="Details",
        help="Indicate the employees to consider in this extra and the amount to each one.",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("approved", "Approved"),
        ],
        help="The extra must be approved to allow pay this on the employee payslips",
        readonly=True,
        copy=False,
        default="draft",
        tracking=True,
    )
    lines_count = fields.Integer(compute="_compute_lines_count")
    company_id = fields.Many2one("res.company", required=True, readonly=True, default=lambda self: self.env.company)

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
            "res_model": "hr.payslip.input.batch.detail",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["id", "in", self.detail_ids.ids]],
            "name": "Lines",
        }
