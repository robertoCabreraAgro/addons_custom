from psycopg2.extensions import AsIs

from odoo import fields, models


class PosLineReport(models.Model):
    _name = "pos.line.report"
    _description = "PoS Report"
    _auto = False
    _order = "date ASC"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
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
    line_id = fields.Many2one(
        comodel_name="pos.order.line",
        readonly=True,
    )
    order_id = fields.Many2one(
        comodel_name="pos.order",
        readonly=True,
    )
    config_id = fields.Many2one(
        comodel_name="pos.config",
        readonly=True,
    )
    date = fields.Date(
        readonly=True,
    )
    year = fields.Integer(
        readonly=True,
    )
    quarter = fields.Integer(
        readonly=True,
    )
    month = fields.Integer(
        readonly=True,
    )
    month_name = fields.Char(
        readonly=True,
    )
    week_of_year = fields.Integer(
        readonly=True,
    )
    day_of_month = fields.Integer(
        readonly=True,
    )
    day_of_week = fields.Integer(
        readonly=True,
    )
    day_of_year = fields.Integer(
        readonly=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        readonly=True,
    )
    product_category_id = fields.Many2one(
        comodel_name="product.category",
        readonly=True,
    )
    manufacturer_id = fields.Many2one(
        comodel_name="res.partner",
        string="Manufacturer",
        readonly=True,
    )
    parent_state = fields.Selection(
        selection=[
            ("draft", "New"),
            ("cancel", "Cancelled"),
            ("paid", "Paid"),
            ("done", "Posted"),
            ("invoiced", "Invoiced"),
        ],
        string="State",
        readonly=True,
    )

    ref = fields.Char(
        readonly=True,
    )
    name = fields.Char(
        readonly=True,
    )

    quantity = fields.Float(
        readonly=True,
    )
    price_unit = fields.Float(
        readonly=True,
    )
    discount = fields.Float(
        readonly=True,
    )
    price_subtotal = fields.Float(
        string="Subtotal",
        readonly=True,
    )
    price_total = fields.Float(
        string="Total",
        readonly=True,
    )
    purchase_price = fields.Float(
        readonly=True,
    )
    purchase_price_total = fields.Float(
        string="Total Purchase",
        readonly=True,
    )
    margin = fields.Float(
        readonly=True,
    )
    margin_percent = fields.Float(
        readonly=True,
    )

    # ------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------

    def init(self):
        table = AsIs(self._table)
        query = AsIs(self._query())
        self.env.cr.execute(f"DROP MATERIALIZED view IF EXISTS {table} CASCADE")
        if self.env.context.get("with_data"):
            # When calling with that context it will create the view and populate it
            self.env.cr.execute(f"CREATE MATERIALIZED VIEW {table} AS ({query})")
        else:
            # To avoid long time to update the module we create the view without data
            # and later be populated by the cron that executes the method refresh()
            self.env.cr.execute(
                f"CREATE MATERIALIZED VIEW {table} AS ({query}) WITH NO DATA"
            )
        self.env.cr.execute(f"CREATE UNIQUE INDEX id_{table} ON {table} (line_id)")

    # ------------------------------------------------------------
    # SQL
    # ------------------------------------------------------------

    def _query(self):
        return """
            WITH pols AS (
                SELECT
                    pol.id,
                    pol.id as line_id,
                    pol.order_id,
                    po.company_id,
                    po.partner_id,
                    pol.product_id,
                    po.state AS parent_state,
                    po.pos_reference AS ref,
                    pol.name,
                    po.date_order AS date,
                    pol.qty AS quantity,
                    pol.price_unit,
                    pol.price_subtotal,
                    pol.price_subtotal_incl AS price_total,
                    pol.discount,
                    COALESCE(pol.price_cost, 0.0) AS purchase_price,
                    (COALESCE(pol.price_cost, 0.0) * COALESCE(pol.qty, 0.0)) AS purchase_price_total,
                    pol.margin,
                    pol.margin_percent,
                    po.config_id,
                    pt.categ_id AS product_category_id,
                    EXTRACT(YEAR FROM po.date_order) AS year,
                    EXTRACT(MONTH FROM po.date_order) AS month,
                    TO_CHAR(po.date_order, 'Month') AS month_name,
                    EXTRACT(QUARTER FROM po.date_order) AS quarter,
                    EXTRACT(WEEK FROM po.date_order) AS week_of_year,
                    EXTRACT(DAY FROM po.date_order) AS day_of_month,
                    EXTRACT(DOW FROM po.date_order) AS day_of_week,
                    EXTRACT(DOY FROM po.date_order) AS day_of_year
                FROM
                    pos_order_line AS pol
                INNER JOIN
                    pos_order AS po
                    ON po.id = pol.order_id
                INNER JOIN
                    product_product AS pp
                    ON pp.id = pol.product_id
                INNER JOIN
                    product_template AS pt
                    ON pt.id = pp.product_tmpl_id
            )
            SELECT
                *
            FROM
                pols
            ORDER BY
                date ASC,
                order_id ASC,
                line_id ASC
        """

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

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
