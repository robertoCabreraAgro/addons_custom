from psycopg2.extensions import AsIs

from odoo import fields, models
from odoo.addons.account.models.account_move import PAYMENT_STATE_SELECTION


class InvoiceLineOut(models.Model):
    _name = "invoice.line.out.report"
    _description = "Invoice Line Out"
    _auto = False
    _order = 'date DESC'


    company_id = fields.Many2one("res.company", readonly=True)
    move_id = fields.Many2one("account.move", readonly=True)
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
    journal_id = fields.Many2one("account.journal", readonly=True)
    x_treatment = fields.Selection(
        [
            ("not_fiscal_simulated", "Not Fiscal simulated"),
            ("not_fiscal_real", "Not Fiscal real"),
            ("fiscal_simulated", "Fiscal simulated"),
            ("fiscal_real", "Fiscal real"),
        ],
        "Treatment",
        readonly=True,
    )
    partner_id = fields.Many2one("res.partner", readonly=True)
    commercial_partner_id = fields.Many2one("res.partner", readonly=True)
    invoice_user_id = fields.Many2one("res.users", readonly=True)
    team_id = fields.Many2one("crm.team", readonly=True)
    date = fields.Date(readonly=True)
    year = fields.Integer(readonly=True)
    quarter = fields.Integer(readonly=True)
    month = fields.Integer(readonly=True)
    month_name = fields.Char(readonly=True)
    week_of_year = fields.Integer(readonly=True)
    day_of_year = fields.Integer(readonly=True)
    day_of_month = fields.Integer(readonly=True)
    day_of_week = fields.Integer(readonly=True)
    invoice_payment_term_id = fields.Many2one("account.payment.term", readonly=True)
    payment_state = fields.Selection(
        selection=PAYMENT_STATE_SELECTION,
        string="Payment Status",
        readonly=True,
    )
    product_id = fields.Many2one("product.product", readonly=True)
    product_categ_id = fields.Many2one("product.category", readonly=True)
    parent_categ_id = fields.Many2one("product.category", string="Parent Category", readonly=True)
    root_categ_id = fields.Many2one("product.category", string="Root Category", readonly=True)
    quantity = fields.Float(readonly=True)
    price_unit = fields.Float(readonly=True)
    discount = fields.Float(readonly=True)
    price_subtotal = fields.Float("Subtotal", readonly=True)
    price_total = fields.Float("Total", readonly=True)
    purchase_price = fields.Float(readonly=True)
    purchase_price_total = fields.Float("Total Purchase", readonly=True)
    margin = fields.Float(readonly=True)
    margin_percent = fields.Float(readonly=True)


    def _query(self):
        return """
            SELECT
                aml.id,
                move.company_id,
                aml.move_id,
                move.move_type,
                aml.journal_id,
                journal.x_treatment,
                move.commercial_partner_id,
                move.partner_id,
                move.invoice_user_id,
                move.team_id,
                move.invoice_date AS date, 
                EXTRACT(YEAR FROM move.invoice_date) AS year,
                EXTRACT(MONTH FROM move.invoice_date) AS month,
                TO_CHAR(move.invoice_date, 'Month') AS month_name,
                EXTRACT(QUARTER FROM move.invoice_date) AS quarter,
                EXTRACT(WEEK FROM move.invoice_date) AS week_of_year,
                EXTRACT(DAY FROM move.invoice_date) AS day_of_month,
                EXTRACT(DOW FROM move.invoice_date) AS day_of_week,
                EXTRACT(DOY FROM move.invoice_date) AS day_of_year,
                move.invoice_payment_term_id,
                move.payment_state,
                aml.sequence,
                aml.product_id,
                pc.id AS product_categ_id,
                CASE
                    WHEN pc.parent_id = pc.root_categ_id THEN pc.id
                    ELSE pc.parent_id
                    END AS parent_categ_id,
                pc.root_categ_id,
                aml.quantity,
                aml.price_unit,
                aml.discount,
                aml.price_subtotal,
                aml.price_total,
                aml.purchase_price,
                ROUND((aml.purchase_price * quantity), 2) AS purchase_price_total,
                aml.margin,aml.margin_percent
            FROM
                account_move_line aml
                INNER JOIN account_move move ON move.id = aml.move_id
                LEFT JOIN account_journal journal ON journal.id = aml.journal_id
                LEFT JOIN product_product pp ON pp.id = aml.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN product_category pc ON pc.id = pt.categ_id
            WHERE
                move.move_type IN ('out_invoice', 'out_refund')
                AND move."state" = 'posted'
                AND journal.x_treatment IN ('fiscal_real', 'not_fiscal_real')
                AND aml.display_type = 'product'
                AND aml.quantity != 0.0
            ORDER BY
                move.invoice_date, move.id
        """

    def _check_is_populated(self, table):
        self._cr.execute(
            f"SELECT relispopulated FROM pg_class WHERE relname = '{table}' and relkind = 'm'"
        )
        res = self._cr.fetchone()
        return res and res[0]

    def refresh_concurrently(self):
        table = AsIs(self._table)
        if not self._check_is_populated(table):
            self._cr.execute(f"REFRESH MATERIALIZED VIEW {table}")
            return

        self._cr.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {table}")

    def init(self):
        table = AsIs(self._table)
        query = AsIs(self._query())
        self._cr.execute(f"DROP MATERIALIZED view IF EXISTS {table} CASCADE")
        if self._context.get("with_data"):
            # When calling with that context it will create the view and populate it
            self._cr.execute(
                f"CREATE MATERIALIZED VIEW {table} AS ({query})"
            )
        else:
            # To avoid long time to update the module we create the view without data
            # and later be populated by the cron that executes the method refresh_concurrently()
            self._cr.execute(
                f"CREATE MATERIALIZED VIEW {table} AS ({query}) WITH NO DATA"
            )
        self._cr.execute(f"CREATE UNIQUE INDEX id_{table} ON {table} (id)")
