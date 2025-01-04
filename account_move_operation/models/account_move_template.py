from odoo import api, fields, models


class AccountMoveTemplate(models.Model):
    _inherit = "account.move.template"

    move_type = fields.Selection(
        selection=[
            ("entry", "Journal Entry"),
            ("out_invoice", "Customer Invoice"),
            ("out_refund", "Customer Credit Note"),
            ("in_invoice", "Vendor Bill"),
            ("in_refund", "Vendor Credit Note"),
            ("out_receipt", "Sales Receipt"),
            ("in_receipt", "Purchase Receipt"),
        ],
        string="Type",
        default="entry",
        required=True,
    )
    company_currency_id = fields.Many2one(
        string="Company Currency",
        related="company_id.currency_id",
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        "Currency",
        compute="_compute_currency_id",
        store=True,
        readonly=False,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Partner",
        domain=["|", ("parent_id", "=", False), ("is_company", "=", True)],
    )
    line_ids_integrity = fields.Binary(compute="_compute_line_ids_integrity")
    post = fields.Boolean(help="Set true if want to post the entry as it is created.")

    @api.depends("line_ids")
    def _compute_line_ids_integrity(self):
        for template in self:
            sequence2amount = {}
            for line in template.line_ids:
                sequence2amount[line.sequence] = line.amount
            template.line_ids_integrity = sequence2amount

    def prepare_wizard_values(self):
        vals = {
            "partner_id": self.partner_id.id or False,
            "journal_id": self.journal_id.id,
            "currency_id": self.currency_id.id,
            "move_type": self.move_type,
            "state": "set_lines",
            "ref": self.ref,
            "post": self.post,
        }
        if self._context.get("default_partner_id"):
            vals["partner_id"] = self._context.get("default_partner_id")
        if self.env.context.get("operation_id"):
            operation = self.env["account.move.operation"].browse(self.env.context.get("operation_id"))
            if not vals.get("currency_id") and operation.currency_id:
                vals["currency_id"] = operation.currency_id.id
            if not vals.get("partner_id"):
                vals["partner_id"] = operation.partner_id.id
            line = self.env["account.move.operation.line"].browse(self.env.context.get("operation_line_id"))
            if line and line.date_last_document:
                date_last_document = line._get_latest_document_date()
                if date_last_document:
                    vals["date"] = date_last_document
        return vals

    def generate_journal_entry(self):
        self.ensure_one()
        if self.move_type == "entry":
            return super().generate_journal_entry()
        wiz = self.env["account.invoice.template.run"].create({"template_id": self.id})
        wiz._onchange_template_id()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account_move_operation.account_invoice_template_run_action"
        )
        action.update({"res_id": wiz.id})
        return action
