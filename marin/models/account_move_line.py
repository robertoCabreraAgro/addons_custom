from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Extended fields
    move_type = fields.Selection(store=True)
    # New fields
    fleet_vehicle_log_services_ids = fields.One2many(
        "fleet.vehicle.log.services", "move_line_id", "Fleet services logs"
    )
    allowed_purchase_line_ids = fields.Many2many(
        comodel_name="purchase.order.line",
        string="Allowed purchase lines to be related",
        compute="_compute_allowed_purchase_line_ids",
    )
    allowed_sale_line_ids = fields.Many2many(
        comodel_name="sale.order.line",
        string="Allowed sale lines to be related",
        compute="_compute_allowed_sale_line_ids",
    )

    # Override original method
    def _check_constrains_account_id_journal_id(self):
        self.flush_recordset()
        for line in self.filtered(lambda x: x.display_type not in ("line_section", "line_note")):
            account = line.account_id
            journal = line.move_id.journal_id
            # Changes here
            parent_state = line.parent_state

            if account.deprecated and not self.env.context.get("skip_account_deprecation_check"):
                raise UserError(_("The account %s (%s) is deprecated.", account.name, account.code))

            account_currency = account.currency_id
            if (
                account_currency
                and account_currency != line.company_currency_id
                and account_currency != line.currency_id
            ):
                raise UserError(
                    _(
                        "The account selected on your journal entry forces to provide a secondary currency. "
                        "You should remove the secondary currency on the account."
                    )
                )
            # Changes made between
            if account.allowed_journal_ids and journal not in account.allowed_journal_ids and parent_state == "posted":
                raise UserError(
                    _(
                        'You cannot use the account (%s) in the journal (%s), check the field "Allowed Journals" '
                        "on the related account.",
                        account.display_name,
                        journal.name,
                    )
                )
            #

            if account in (journal.default_account_id, journal.suspense_account_id):
                continue

            # Changes made between
            if journal.account_control_ids and account not in journal.account_control_ids and parent_state == "posted":
                raise UserError(
                    _(
                        'You cannot use the account (%s) in the journal (%s), check the section "Control-Access" '
                        'under tab "Advanced Settings" on the related journal.',
                        account.display_name,
                        journal.name,
                    )
                )
            #

    # Override original method
    def _compute_account_id(self):
        term_lines = self.filtered(lambda line: line.display_type == "payment_term")
        if term_lines:
            journals = term_lines.journal_id
            moves = term_lines.move_id
            self.env.cr.execute(
                """
                WITH previous AS (
                    SELECT DISTINCT ON (l.move_id)
                        'account.move' AS model,
                        l.move_id AS id,
                        NULL AS account_type,
                        l.account_id AS account_id
                    FROM account_move_line l
                    WHERE l.move_id = ANY(%(move_ids)s)
                        AND l.display_type = 'payment_term'
                        AND l.id != ANY(%(current_ids)s)
                ),
                properties AS (
                    SELECT DISTINCT ON (p.company_id, p.name, p.res_id)
                        'res.partner' AS model,
                        SPLIT_PART(p.res_id, ',', 2)::integer AS id,
                        CASE
                            WHEN p.name = 'property_account_receivable_id' THEN 'asset_receivable'
                            ELSE 'liability_payable'
                        END AS account_type,
                        SPLIT_PART(p.value_reference, ',', 2)::integer AS account_id
                    FROM ir_property p
                    --JOIN res_company c ON p.company_id = c.id
                    WHERE p.name IN ('property_account_receivable_id', 'property_account_payable_id')
                        AND p.company_id = ANY(%(company_ids)s)
                        AND p.res_id = ANY(%(partners)s)
                    ORDER BY p.company_id, p.name, p.res_id, account_id
                ),
                default_journal AS (
                    SELECT
                        'account.journal' AS model,
                        j.id AS id,
                        CASE
                            WHEN j.type = 'sale' THEN 'asset_receivable'
                            ELSE 'liability_payable'
                        END AS account_type,
                        CASE
                            WHEN j.type = 'sale' THEN j.default_receivable_account_id
                            ELSE j.default_payable_account_id
                        END AS account_id
                    FROM account_journal j
                    WHERE j.type IN ('sale', 'purchase')
                        AND j.company_id = ANY(%(company_ids)s)
                        AND (j.default_payable_account_id IS NOT NULL OR j.default_receivable_account_id IS NOT NULL)
                        AND j.id = ANY(%(journal_ids)s)
                ),
                default_properties AS (
                    SELECT DISTINCT ON (p.company_id, p.name)
                        'res.partner' AS model,
                        c.partner_id AS id,
                        CASE
                            WHEN p.name = 'property_account_receivable_id' THEN 'asset_receivable'
                            ELSE 'liability_payable'
                        END AS account_type,
                        SPLIT_PART(p.value_reference, ',', 2)::integer AS account_id
                    FROM ir_property p
                    JOIN res_company c ON p.company_id = c.id
                    WHERE p.name IN ('property_account_receivable_id', 'property_account_payable_id')
                        AND p.company_id = ANY(%(company_ids)s)
                        AND p.res_id IS NULL
                    ORDER BY p.company_id, p.name, account_id
                ),
                fallback AS (
                    SELECT DISTINCT ON (a.company_id, a.account_type)
                        'res.company' AS model,
                        a.company_id AS id,
                        a.account_type AS account_type,
                        a.id AS account_id
                    FROM account_account a
                    WHERE a.company_id = ANY(%(company_ids)s)
                        AND a.account_type IN ('asset_receivable', 'liability_payable')
                        AND a.deprecated = 'f'
                )
                SELECT * FROM previous
                UNION ALL
                SELECT * FROM properties
                UNION ALL
                SELECT * FROM default_journal
                UNION ALL
                SELECT * FROM default_properties
                UNION ALL
                SELECT * FROM fallback
            """,
                {
                    "company_ids": moves.company_id.ids,
                    "journal_ids": journals.ids,
                    "move_ids": moves.ids,
                    "partners": [f"res.partner,{pid}" for pid in moves.commercial_partner_id.ids],
                    "current_ids": term_lines.ids,
                },
            )
            accounts = {
                (model, id, account_type): account_id for model, id, account_type, account_id in self.env.cr.fetchall()
            }
            for line in term_lines:
                account_type = (
                    "asset_receivable" if line.move_id.is_sale_document(include_receipts=True) else "liability_payable"
                )
                journal = line.move_id.journal_id
                move = line.move_id
                account_id = (
                    accounts.get(("account.move", move.id, None))
                    or accounts.get(("res.partner", move.commercial_partner_id.id, account_type))
                    or accounts.get(("account.journal", journal.id, account_type))
                    or accounts.get(("res.partner", move.company_id.partner_id.id, account_type))
                    or accounts.get(("res.company", move.company_id.id, account_type))
                )
                if line.move_id.fiscal_position_id:
                    account_id = self.move_id.fiscal_position_id.map_account(
                        self.env["account.account"].browse(account_id)
                    )
                line.account_id = account_id

        product_lines = self.filtered(lambda line: line.display_type == "product" and line.move_id.is_invoice(True))
        if product_lines:
            for line in product_lines:
                if line.product_id:
                    fiscal_position = line.move_id.fiscal_position_id
                    accounts = line.with_company(line.company_id).product_id.product_tmpl_id.get_product_accounts(
                        fiscal_pos=fiscal_position
                    )
                    if line.move_id.move_type in ("out_invoice", "out_receipt"):
                        line.account_id = accounts["income"] or journal.default_account_id or line.account_id
                    elif line.move_id.move_type == "out_refund":
                        line.account_id = (
                            accounts["income_refund"] or journal.default_refund_account_id or line.account_id
                        )
                    elif line.move_id.move_type in ("in_invoice", "in_receipt"):
                        line.account_id = accounts["expense"] or journal.default_account_id or line.account_id
                    elif line.move_id.move_type == "in_refund":
                        line.account_id = (
                            accounts["expense_refund"] or journal.default_refund_account_id or line.account_id
                        )
                elif line.partner_id:
                    line.account_id = self.env["account.account"]._get_most_frequent_account_for_partner(
                        company_id=line.company_id.id,
                        partner_id=line.partner_id.id,
                        move_type=line.move_id.move_type,
                    )

        for line in self.filtered(
            lambda ln: not ln.account_id and ln.display_type not in ("line_section", "line_note")
        ):
            previous_two_accounts = line.move_id.line_ids.filtered(
                lambda x: x.account_id and x.display_type == line.display_type
            )[-2:].account_id
            if len(previous_two_accounts) == 1 and len(line.move_id.line_ids) > 2:
                line.account_id = previous_two_accounts
            else:
                line.account_id = line.move_id.journal_id.default_account_id

    # Extend original method
    def _prepare_analytic_distribution_line(self, distribution, account_id, distribution_on_each_plan):
        res = super()._prepare_analytic_distribution_line(distribution, account_id, distribution_on_each_plan)
        sign = -1 if res["amount"] < 0 else 1
        res.update(
            {
                "amount_taxinc": self.price_total * sign,
                "date_impacted": self.date,
                "vehicle_id": self.vehicle_id and self.vehicle_id.id or False,
            }
        )
        return res

    def _prepare_compute_analytic_distribution(self):
        return {
            "product_id": self.product_id.id,
            "product_categ_id": self.product_id.categ_id.id,
            "partner_id": self.partner_id.id,
            "partner_category_id": self.partner_id.category_id.ids,
            "account_prefix": self.account_id.code,
            "company_id": self.company_id.id,
            "vehicle_id": self.vehicle_id.id,
        }

    # Extend original method
    @api.depends("account_id", "partner_id", "product_id", "vehicle_id")
    def _compute_analytic_distribution(self):
        if self.vehicle_id:
            for line in self:
                if line.display_type == "product" or not line.move_id.is_invoice(include_receipts=True):
                    vals = line._prepare_compute_analytic_distribution()
                    distribution = self.env["account.analytic.distribution.model"]._get_distribution(vals)
                    line.analytic_distribution = distribution or line.analytic_distribution
        return super()._compute_analytic_distribution()

    # Extend original method
    def _prepare_fleet_log_service(self):
        res = super()._prepare_fleet_log_service()
        res.update({"move_line_id": self.id})
        return res

    def _get_po_line_candidate(self, po_lines):
        lines = sorted(po_lines, key=lambda line: (line.price_unit, line.qty_to_invoice), reverse=True)
        for line in lines:
            qty = (
                line.qty_to_invoice
                if not self.product_uom_id or line.product_uom == self.product_uom_id
                else (line.product_uom._compute_quantity(line.qty_to_invoice, self.product_uom_id))
            )
            if qty >= self.quantity:
                return line
        return False

    @api.depends(
        "move_id.related_purchase_order_id",
        "move_id.relate_purchase_order",
        "move_id.partner_id",
        "move_id.line_ids.purchase_line_id",
    )
    def _compute_allowed_purchase_line_ids(self):
        purchase_obj = self.env["purchase.order"]
        for rec in self:
            move = rec.move_id
            orders = (
                move.related_purchase_order_id
                if move.related_purchase_order_id and move.relate_purchase_order
                else purchase_obj.search([("partner_id", "=", move.partner_id.id)])
            )
            rec.allowed_purchase_line_ids = orders.order_line | move.line_ids.mapped("purchase_line_id")

    @api.onchange("purchase_line_id")
    def _onchange_purchase_line(self):
        for rec in self:
            if rec.purchase_line_id:
                rec.product_id = rec.purchase_line_id.product_id

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
                lines if not rec.product_id else lines.filtered(lambda line: line.product_id == rec.product_id)
            )
