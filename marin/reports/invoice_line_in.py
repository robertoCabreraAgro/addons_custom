from psycopg2.extensions import AsIs

from odoo import fields, models
from odoo.addons.account.models.account_move import PAYMENT_STATE_SELECTION


class InvoiceLineIn(models.Model):
    _name = "invoice.line.in.report"
    _description = "Invoice Line In"
    _auto = False
    _order = "payment_reference ASC, date ASC"

    aml_id = fields.Many2one("account.move.line", readonly=True)
    move_id = fields.Many2one("account.move", readonly=True)
    journal_id = fields.Many2one("account.journal", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    product_id = fields.Many2one("product.product", readonly=True)
    product_category_id = fields.Many2one(
        "product.category", string="Product Category", readonly=True
    )
    parent_categ_id = fields.Many2one(
        "product.category", string="Parent Category", readonly=True
    )
    root_categ_id = fields.Many2one(
        "product.category", string="Root Category", readonly=True
    )
    sequence = fields.Integer(readonly=True)
    move_name = fields.Char("Name", readonly=True)
    parent_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("cancel", "Cancelled"),
        ],
        string="State",
        readonly=True,
    )
    ref = fields.Char(readonly=True)
    name = fields.Char(readonly=True)
    display_type = fields.Selection(
        selection=[
            ("product", "Product"),
            ("cogs", "Cost of Goods Sold"),
            ("tax", "Tax"),
            ("discount", "Discount"),
            ("rounding", "Rounding"),
            ("payment_term", "Payment Term"),
            ("line_section", "Section"),
            ("line_note", "Note"),
            ("epd", "Early Payment Discount"),
        ],
        readonly=True,
    )
    date = fields.Date(readonly=True)
    quantity = fields.Float(readonly=True)
    price_unit = fields.Float(readonly=True)
    price_subtotal = fields.Float("Subtotal", readonly=True)
    price_total = fields.Float("Total", readonly=True)
    discount = fields.Float(readonly=True)
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
    payment_reference = fields.Char(readonly=True)
    payment_state = fields.Selection(
        selection=PAYMENT_STATE_SELECTION,
        string="Payment Status",
        readonly=True,
    )
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

    def _query(self):
        return """
            WITH amls AS (
                SELECT
                    id,
                    id as aml_id,
                    move_id,
                    journal_id,
                    company_id,
                    sequence,
                    partner_id,
                    product_id,
                    move_name,
                    parent_state,
                    ref,
                    name,
                    display_type,
                    date,
                    quantity,
                    price_unit,
                    price_subtotal,
                    price_total,
                    discount
                FROM
                    account_move_line
                WHERE
                    display_type = 'product'
            ),
            inv_amls AS (
                SELECT
                    amls.*,
                    inv.move_type,
                    inv.payment_reference,
                    inv.payment_state
                FROM
                    amls
                LEFT OUTER JOIN
                    account_move AS inv
                    ON amls.move_id = inv.id
                WHERE
                    inv.move_type in ('in_invoice', 'in_refund')
                    AND amls.date > '2019-12-31'
            ),
            product_amls AS (
                SELECT
                    inv_amls.*,
                    pt.name AS product_name,
                    pt.categ_id AS product_category_id,
                    CASE
                        WHEN pc.parent_id = pc.root_categ_id THEN pc.id
                        ELSE pc.parent_id
                    END AS parent_categ_id,
                    pc.root_categ_id
                FROM
                    inv_amls
                LEFT OUTER JOIN
                    product_product AS pp
                    ON inv_amls.product_id = pp.id
                LEFT OUTER JOIN
                    product_template AS pt
                    ON pp.product_tmpl_id = pt.id
                LEFT OUTER JOIN
                    product_category AS pc
                    ON pc.id = pt.categ_id
            ),
            journal_amls AS (
                SELECT
                    product_amls.*,
                    aj.name AS journal_name,
                    x_treatment
                FROM
                    product_amls
                LEFT OUTER JOIN
                    account_journal AS aj
                    ON product_amls.journal_id = aj.id
            ),
            company_amls AS (
                SELECT
                    journal_amls.*,
                    rc.name AS company_name
                FROM
                    journal_amls
                LEFT OUTER JOIN
                    res_company AS rc
                    ON journal_amls.company_id = rc.id
            ),
            partner_amls AS (
                SELECT
                    company_amls.*,
                    rp.name AS partner_name
                FROM
                    company_amls
                LEFT OUTER JOIN
                    res_partner AS rp
                    ON company_amls.partner_id = rp.id
            )
            SELECT
                *
            FROM
                partner_amls
            ORDER BY
                payment_reference,
                date
        """

    def _is_populated(self, table):
        self._cr.execute(
            f"SELECT relispopulated FROM pg_class WHERE relname = '{table}' and relkind = 'm'"
        )
        res = self._cr.fetchone()
        return res and res[0]

    def refresh(self):
        table = AsIs(self._table)
        command = f"REFRESH MATERIALIZED VIEW {"CONCURRENTLY" if self._is_populated() else ""} {table}"
        self._cr.execute(command)

    def init(self):
        table = AsIs(self._table)
        query = AsIs(self._query())
        self._cr.execute(f"DROP MATERIALIZED view IF EXISTS {table} CASCADE")
        if self._context.get("with_data"):
            # When calling with that context it will create the view and populate it
            self._cr.execute(
                f"CREATE MATERIALIZED VIEW {table} AS ({query})",
            )
        else:
            # To avoid long time to update the module we create the view without data
            # and later be populated by the cron that executes the method refresh()
            self._cr.execute(
                f"CREATE MATERIALIZED VIEW {table} AS ({query}) WITH NO DATA",
            )
        self._cr.execute(f"CREATE UNIQUE INDEX id_{table} ON {table} (aml_id)")
