from psycopg2.extensions import AsIs

from odoo import fields, models
from odoo.tools import SQL
from odoo.tools.query import Query

from odoo.addons.account.models.account_move import PAYMENT_STATE_SELECTION


class InvoiceLineOut(models.Model):
    _name = "invoice.line.out.report"
    _description = "Invoice Line Out"
    _auto = False
    _order = "invoice_date DESC"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        readonly=True,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
        readonly=True,
    )
    x_treatment = fields.Selection(
        [
            ("not_fiscal_simulated", "Not Fiscal simulated"),
            ("not_fiscal_real", "Not Fiscal real"),
            ("fiscal_simulated", "Fiscal simulated"),
            ("fiscal_real", "Fiscal real"),
        ],
        string="Treatment",
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        readonly=True,
    )
    commercial_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Main Partner",
        readonly=True,
    )
    invoice_payment_term_id = fields.Many2one(
        comodel_name="account.payment.term",
        readonly=True,
    )
    invoice_user_id = fields.Many2one(
        comodel_name="res.users",
        readonly=True,
    )
    team_id = fields.Many2one(
        comodel_name="crm.team",
        string="Team",
        readonly=True,
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Entry",
        readonly=True,
    )
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
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("posted", "Open"),
            ("cancel", "Cancelled"),
        ],
        string="Invoice Status",
        readonly=True,
    )
    payment_state = fields.Selection(
        selection=PAYMENT_STATE_SELECTION,
        string="Payment Status",
        readonly=True,
    )
    invoice_date = fields.Date(readonly=True)
    year = fields.Integer(readonly=True)
    quarter = fields.Integer(readonly=True)
    month = fields.Integer(readonly=True)
    month_name = fields.Char(readonly=True)
    week_of_year = fields.Integer(readonly=True)
    day_of_year = fields.Integer(readonly=True)
    day_of_month = fields.Integer(readonly=True)
    day_of_week = fields.Integer(readonly=True)

    # Product fields
    product_id = fields.Many2one(
        comodel_name="product.product",
        readonly=True,
    )
    product_category_id = fields.Many2one(
        comodel_name="product.category",
        readonly=True,
    )
    parent_categ_id = fields.Many2one(
        comodel_name="product.category",
        string="Parent Category",
        readonly=True,
    )
    root_categ_id = fields.Many2one(
        comodel_name="product.category",
        string="Root Category",
        readonly=True,
    )
    manufacturer_id = fields.Many2one(
        comodel_name="res.partner",
        string="Manufacturer",
        readonly=True,
    )

    # ?? fields
    quantity = fields.Float(readonly=True)
    price_unit = fields.Float(readonly=True, aggregator="avg")
    discount = fields.Float(readonly=True, aggregator="avg")
    price_subtotal = fields.Float("Subtotal", readonly=True)
    price_total = fields.Float("Total", readonly=True)
    purchase_price = fields.Float(readonly=True, aggregator="avg")
    purchase_price_total = fields.Float("Total Purchase", readonly=True)
    margin = fields.Float(readonly=True)
    margin_percent = fields.Float(readonly=True, aggregator="avg")

    # Collection fields
    collected_quantity = fields.Float(readonly=True)
    collected_price_subtotal = fields.Float(readonly=True)
    collected_price_total = fields.Float(readonly=True)
    collected_purchase_price_total = fields.Float(readonly=True)
    collected_margin = fields.Float(readonly=True)

    # ------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------

    def init(self):
        table = AsIs(self._table)
        query = AsIs(self._query())
        self._cr.execute(f"DROP MATERIALIZED VIEW IF EXISTS {table} CASCADE")
        command = f"CREATE MATERIALIZED VIEW {table} AS ({query})"
        if not self._context.get("with_data"):
            # When calling with that context it will create the view and populate it
            # To avoid long time to update the module we create the view without data
            # and later be populated by the cron that executes the method refresh()
            command += " WITH NO DATA"
        self._cr.execute(command)
        self._cr.execute(f"CREATE UNIQUE INDEX id_{table} ON {table} (id)")

    # ------------------------------------------------------------
    # SQL
    # ------------------------------------------------------------

    def _query(self):
        return f"SELECT {self._select()} FROM {self._from()} WHERE {self._where()}"

    def _select(self):
        return """
            aml.id,
            aml.move_id,
            move.company_id,
            move.journal_id,
            journal.x_treatment,
            move.currency_id,
            move.commercial_partner_id,
            move.partner_id,
            move.invoice_payment_term_id,
            move.invoice_user_id,
            move.team_id,
            move.payment_state,
            move.invoice_date, 
            EXTRACT(YEAR FROM move.invoice_date) AS year,
            EXTRACT(MONTH FROM move.invoice_date) AS month,
            TO_CHAR(move.invoice_date, 'Month') AS month_name,
            EXTRACT(QUARTER FROM move.invoice_date) AS quarter,
            EXTRACT(WEEK FROM move.invoice_date) AS week_of_year,
            EXTRACT(DAY FROM move.invoice_date) AS day_of_month,
            EXTRACT(DOW FROM move.invoice_date) AS day_of_week,
            EXTRACT(DOY FROM move.invoice_date) AS day_of_year,
            move.move_type,
            move.state,
            aml.product_id,
            pc.id AS product_category_id,
            CASE
                WHEN pc.parent_id = pc.root_categ_id
                THEN pc.id
                ELSE pc.parent_id
            END AS parent_categ_id,
            pc.root_categ_id,
            manufacturer.id AS manufacturer_id,
            aml.quantity,
            aml.price_unit,
            aml.discount,
            aml.price_subtotal,
            aml.price_total,
            aml.purchase_price,
            ROUND((aml.purchase_price * quantity), 2) AS purchase_price_total,
            aml.margin,
            aml.margin_percent,

            -- Collected values
            aml.quantity * COALESCE(
                (move.amount_total - move.amount_residual) / NULLIF(move.amount_total, 0.0),
                0
            ) AS collected_quantity,
            aml.price_subtotal * COALESCE(
                (move.amount_total - move.amount_residual) / NULLIF(move.amount_total, 0.0),
                0
            ) AS collected_price_subtotal,
            aml.price_total * COALESCE(
                (move.amount_total - move.amount_residual) / NULLIF(move.amount_total, 0.0),
                0
            ) AS collected_price_total,
            aml.purchase_price * quantity * COALESCE(
                (move.amount_total - move.amount_residual) / NULLIF(move.amount_total, 0.0),
                0
            ) AS collected_purchase_price_total,
            aml.margin * COALESCE(
                (move.amount_total - move.amount_residual) / NULLIF(move.amount_total, 0.0),
                0
            ) AS collected_margin
        """

    def _from(self):
        return """
            account_move_line aml
            INNER JOIN account_move move
                ON aml.move_id=move.id
                LEFT JOIN account_journal journal
                    ON move.journal_id=journal.id
            LEFT JOIN product_product pp
                ON aml.product_id=pp.id
                LEFT JOIN product_template pt
                    ON pp.product_tmpl_id=pt.id
                    LEFT JOIN product_category pc
                        ON pt.categ_id=pc.id
                    LEFT JOIN res_partner manufacturer
                        ON pt.manufacturer_id=manufacturer.id
        """

    def _where(self):
        return """
            move.move_type IN ('out_invoice', 'out_refund')
            AND move.state = 'posted'
            AND journal.x_treatment IN ('fiscal_real', 'not_fiscal_real')
            AND aml.display_type = 'product'
        """

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _read_group_select(self, aggregate_spec: str, query: Query) -> SQL:
        """This override allows us to correctly calculate the average price of products."""
        if aggregate_spec == "price_unit:avg":
            return SQL(
                """
                COALESCE(
                    SUM(%(f_price)s) / NULLIF(SUM(%(f_qty)s), 0.0),
                    0
                )
                """,
                f_price=self._field_to_sql(self._table, "price_subtotal", query),
                f_qty=self._field_to_sql(self._table, "quantity", query),
            )

        elif aggregate_spec == "purchase_price:avg":
            return SQL(
                """
                COALESCE(
                    SUM(%(f_price)s) / NULLIF(SUM(%(f_qty)s), 0.0),
                    0
                )
                """,
                f_price=self._field_to_sql(self._table, "purchase_price_total", query),
                f_qty=self._field_to_sql(self._table, "quantity", query),
            )

        elif aggregate_spec == "margin_percent:avg":
            return SQL(
                """
                COALESCE(
                    SUM(%(f_margin)s) / NULLIF(SUM(%(f_subtotal)s), 0.0),
                    0
                )
                """,
                f_margin=self._field_to_sql(self._table, "margin", query),
                f_subtotal=self._field_to_sql(self._table, "price_subtotal", query),
            )

        else:
            return super()._read_group_select(aggregate_spec, query)

    def refresh(self):
        table = AsIs(self._table)
        command = f"REFRESH MATERIALIZED VIEW {"CONCURRENTLY" if self._is_populated() else ""} {table}"
        self._cr.execute(command)

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------

    def _is_populated(self):
        table = AsIs(self._table)
        self._cr.execute(
            f"SELECT ispopulated FROM pg_matviews WHERE matviewname='{table}'"
        )
        res = self._cr.fetchone()
        return res and res[0]
