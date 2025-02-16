from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import frozendict


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"


    # Extended fields
    move_type = fields.Selection(store=True)

    # New fields
    allowed_sale_line_ids = fields.Many2many(
        comodel_name="sale.order.line",
        string="Allowed sale lines to be related",
        compute="_compute_allowed_sale_line_ids",
    )


    # Override original method
    def _compute_account_id(self):
        term_lines = self.filtered(lambda l: l.display_type == "payment_term")
        if term_lines:
            for line in term_lines:
                line = line.with_company(line.company_id)
                partner_prop = (
                    "property_account_receivable_id"
                    if line.move_id.is_sale_document(include_receipts=True)
                    else "property_account_payable_id"
                )
                journal = line.move_id.journal_id
                journal_prop = (
                    "default_receivable_account_id"
                    if journal.type == "sale"
                    else "default_payable_account_id"
                )
                move = line.move_id
                previous_two_accounts = move.line_ids.filtered(
                    lambda x:
                        x.account_id
                        and x.display_type == "payment_term"
                        and line._origin.id not in x.ids
                )[-2:].account_id
                account_id = (
                    getattr(journal, journal_prop)
                    or getattr(move.partner_id, partner_prop)
                    or getattr(move.commercial_partner_id, partner_prop)
                    or previous_two_accounts
                    or getattr(move.company_id.partner_id, partner_prop)
                )
                if move.fiscal_position_id:
                    account_id = move.fiscal_position_id.map_account(
                        self.env["account.account"].browse(account_id)
                    )
                line.account_id = account_id

        product_lines = self.filtered(
            lambda l: l.display_type == "product" and l.move_id.is_invoice(True)
        )
        if product_lines:
            for line in product_lines:
                journal = line.move_id.journal_id
                if line.product_id:
                    fiscal_position = line.move_id.fiscal_position_id
                    accounts = line.with_company(
                        line.company_id
                    ).product_id.product_tmpl_id.get_product_accounts(
                        fiscal_pos=fiscal_position
                    )
                    if line.move_id.move_type in ("out_invoice", "out_receipt"):
                        line.account_id = (
                            accounts["income"]
                            or journal.default_account_id
                            or line.account_id
                        )
                    elif line.move_id.move_type == "out_refund":
                        line.account_id = (
                            accounts["income_refund"]
                            or journal.default_refund_account_id
                            or line.account_id
                        )
                    elif line.move_id.move_type in ("in_invoice", "in_receipt"):
                        line.account_id = (
                            accounts["expense"]
                            or journal.default_account_id
                            or line.account_id
                        )
                    elif line.move_id.move_type == "in_refund":
                        line.account_id = (
                            accounts["expense_refund"]
                            or journal.default_refund_account_id
                            or line.account_id
                        )
                if not line.product_id and line.partner_id:
                    account_id = self.env["account.account"]._get_most_frequent_account_for_partner(
                        company_id=line.company_id.id,
                        partner_id=line.partner_id.id,
                        move_type=line.move_id.move_type,
                    )
                    if account_id:
                        line.account_id = account_id

        for line in self.filtered(
            lambda l: not l.account_id and l.display_type not in ("line_section", "line_note")
        ):
            previous_two_accounts = line.move_id.line_ids.filtered(
                lambda x: x.account_id and x.display_type == line.display_type
            )[-2:].account_id
            if len(previous_two_accounts) == 1 and len(line.move_id.line_ids) > 2:
                line.account_id = previous_two_accounts
            else:
                line.account_id = line.move_id.journal_id.default_account_id

    def _prepare_compute_analytic_distribution(self):
        return frozendict(
            {
                "account_prefix": self.account_id.code,
                "company_id": self.company_id.id,
                "partner_category_id": self.partner_id.category_id.ids,
                "partner_id": self.partner_id.id,
                "product_categ_id": self.product_id.categ_id.id,
                "product_id": self.product_id.id,
                "vehicle_id": self.vehicle_id.id,
            }
        )

    # Extend original method
    @api.depends("account_id", "partner_id", "product_id", "vehicle_id")
    def _compute_analytic_distribution(self):
        vehicle_lines = self.filtered(
            lambda line:
                line.vehicle_id
                and line.display_type == "product"
        )
        super(AccountMoveLine, self - vehicle_lines)._compute_analytic_distribution()
        cache = {}
        for line in vehicle_lines:
            arguments = line._prepare_compute_analytic_distribution()
            if arguments not in cache:
                cache[arguments] = self.env['account.analytic.distribution.model']._get_distribution(arguments)
            line.analytic_distribution = cache[arguments] or line.analytic_distribution

    @api.depends("move_id.partner_id", "move_id.line_ids.sale_line_ids")
    def _compute_allowed_sale_line_ids(self):
        sale_obj = self.env["sale.order"]
        for rec in self:
            move = rec.move_id
            orders = sale_obj.search(
                [
                    "|",
                    ("partner_id", "=", move.partner_id.id),
                    ("partner_id", "=", move.partner_id.commercial_partner_id.id),
                ]
            )
            lines = orders.order_line | move.line_ids.mapped("sale_line_ids")
            rec.allowed_sale_line_ids = (
                lines if not rec.product_id
                else lines.filtered(lambda line: line.product_id == rec.product_id)
            )

    @api.onchange("purchase_line_id")
    def _onchange_purchase_line(self):
        for rec in self:
            if rec.purchase_line_id:
                rec.product_id = rec.purchase_line_id.product_id

    # Override original method
    def _check_constrains_account_id_journal_id(self):
        self.flush_recordset()
        for line in self.filtered(lambda x: x.display_type not in ("line_section", "line_note")):
            account = line.account_id
            journal = line.move_id.journal_id
            parent_state = line.parent_state # Changes here

            if account.deprecated and not self.env.context.get("skip_account_deprecation_check"):
                raise UserError(_(
                    'The account %(name)s (%(code)s) is deprecated.',
                    name=account.name, code=account.code
                ))

            account_currency = account.currency_id
            if (
                account_currency
                and account_currency != line.company_currency_id
                and account_currency != line.currency_id
            ):
                raise UserError(_(
                    "The account selected on your journal entry forces to provide a secondary currency. "
                    "You should remove the secondary currency on the account."
                ))

            # Change made in the line below
            if account.allowed_journal_ids and journal not in account.allowed_journal_ids and parent_state == "posted":
                raise UserError(_(
                    'You cannot use the account (%s) in the journal (%s), '
                    'check the field "Allowed Journals" on the related account.',
                    account.display_name,
                    journal.name,
                ))

            if account in (journal.default_account_id, journal.suspense_account_id):
                continue

            # Changes made below
            if (
                journal.account_control_ids
                and account not in journal.account_control_ids
                and parent_state == "posted"
            ):
                raise UserError(_(
                    'You cannot use the account (%s) in the journal (%s), check the section '
                    '"Control-Access" under tab "Advanced Settings" on the related journal.',
                    account.display_name,
                    journal.name,
                ))

    # Extend original method
    def _prepare_analytic_distribution_line(
        self, distribution, account_id, distribution_on_each_plan
    ):
        res = super()._prepare_analytic_distribution_line(
            distribution, account_id, distribution_on_each_plan
        )
        sign = -1 if res["amount"] < 0 else 1
        res.update(
            {
                "amount_taxinc": self.price_total * sign,
                "date_impacted": self.date,
                "vehicle_id": self.vehicle_id and self.vehicle_id.id or False,
            }
        )
        return res
