from odoo import api, fields, models
from odoo.exceptions import UserError


class SyngentaCommercialAgreement(models.Model):
    _name = "syngenta.commercial.agreement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Customer purchase agreements with the distributor to earn benefits"


    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company.id,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Customer",
        required=True,
    )
    predecesor_id = fields.Many2one(
        "syngenta.commercial.agreement",
        "Predecesor agreement",
    )
    name = fields.Char(related="partner_id.name", readonly=True)
    number = fields.Char()
    active = fields.Boolean(default=True)
    date_from = fields.Date("From")
    date_to = fields.Date("To")
    agreement_type = fields.Selection(
        [
            ("ally", "Strategic ally"),
            ("big grower", "Big grower"),
            ("ornamentals", "Ornamentals"),
            ("other", "Other"),
        ],
        "Customer type",
    )
    state = fields.Selection(
        [
            ("in_progress", "In Progress"),
            ("closed", "Closed"),
        ],
        "state",
        default="in_progress",
        readonly=True,
    )
    amount = fields.Float(
        "Amount",
        digits=(16, 2),
        help="Amount asigned to the sale agreement that will be used as base for following calculations.",
    )
    amount_reached = fields.Float(
        "Amount reached",
        digits=(16, 2),
        help="Amount asigned to the sale agreement that will be used as base for following calculations.",
    )
    percentage = fields.Float(
        "Percentage",
        digits=(5, 2),
        help="The base percentage of discount that this agreement can asign to the customers purchases.",
    )
    percentage_reached = fields.Float(
        "Percentage reached",
        digits=(5, 2),
        help="The base percentage of discount that this agreement can asign to the customers purchases.",
    )
    notes = fields.Html(
        "Terms and Conditions",
        help="The reach levels with their respective discount must be noted here."
    )
    report_ids = fields.One2many(
        "syngenta.sale.report",
        "agreement_id",
        "Documents",
    )
    count_report = fields.Integer(compute="_compute_count_report")
    report_line_ids = fields.One2many(
        "syngenta.sale.report.line",
        "agreement_id",
        "Sale Lines",
        auto_join=True,
        copy=True,
    )
    count_line = fields.Integer(compute="_compute_count_line")


    @api.depends("name", "date_from", "date_to")
    def _compute_display_name(self):
        for agreement in self.sudo():
            name = agreement.name and agreement.name.split("\n")[0] or ""
            if agreement.date_from and agreement.date_to:
                name = "{} ({} - {})".format(name, agreement.date_from, agreement.date_to)
            agreement.display_name = name

    @api.depends("report_ids")
    def _compute_count_report(self):
        for agreement in self:
            agreement.count_report = len(agreement.report_ids)

    @api.depends("report_line_ids")
    def _compute_count_line(self):
        for agreement in self:
            agreement.count_line = len(agreement.report_line_ids)

    def action_close(self):
        self.state = "closed"

    def action_new_report(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("syngenta_edi.action_syngenta_sale_report")
        action["views"] = [(self.env.ref("syngenta_edi.view_syngenta_sale_report_form").id, "form")]
        action["context"] = {
            "default_agreement_id": self.id,
        }
        return action

    def action_view_reports(self, documents=False):
        if not documents:
            documents = self.mapped("report_ids")
        action = self.env["ir.actions.actions"]._for_xml_id("syngenta_edi.action_syngenta_sale_report")
        if len(documents) > 1:
            action["domain"] = [("id", "in", documents.ids)]
        elif len(documents) == 1:
            form_view = [(self.env.ref("syngenta_edi.view_syngenta_sale_report_form").id, "form")]
            if "views" in action:
                action["views"] = form_view + [(state, view) for state, view in action["views"] if view != "form"]
            else:
                action["views"] = form_view
            action["res_id"] = documents.id
        else:
            action = {"type": "ir.actions.act_window_close"}
        return action

    def action_view_lines(self, lines=False):
        if not lines:
            lines = self.mapped("report_line_ids")
        action = self.env["ir.actions.actions"]._for_xml_id("syngenta_edi.action_syngenta_sale_report_line")
        if len(lines) >= 1:
            action["domain"] = [("id", "in", lines.ids)]
        else:
            action = {"type": "ir.actions.act_window_close"}
        return action
