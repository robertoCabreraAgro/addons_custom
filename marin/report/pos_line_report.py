from psycopg2.extensions import AsIs

from odoo import fields, models


class PosLineReport(models.Model):
    _name = "pos.line.report"
    _description = "PoS Report"
    _auto = False
    _order = "date ASC"


    line_id = fields.Many2one("pos.order.line", readonly=True)
    order_id = fields.Many2one("pos.order", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    commercial_partner_id = fields.Many2one("res.partner", readonly=True)
    product_id = fields.Many2one("product.product", readonly=True)
    product_categ_id = fields.Many2one("product.category", readonly=True)
    config_id = fields.Many2one("pos.config", readonly=True)
    parent_state = fields.Selection(
        selection=[
            ('draft', 'New'),
            ('cancel', 'Cancelled'),
            ('paid', 'Paid'),
            ('done', 'Posted'),
            ('invoiced', 'Invoiced')
        ],
        string="State",
        readonly=True,
    )
    ref = fields.Char(readonly=True)
    name = fields.Char(readonly=True)
    date = fields.Date(readonly=True)
    quantity = fields.Float(readonly=True)
    price_unit = fields.Float(readonly=True)
    price_subtotal = fields.Float("Subtotal", readonly=True)
    price_total = fields.Float("Total", readonly=True)
    discount = fields.Float(readonly=True)
    purchase_price = fields.Float(readonly=True)
    purchase_price_total = fields.Float("Total Purchase", readonly=True)
    margin = fields.Float(readonly=True)
    margin_percent = fields.Float(readonly=True)
    year = fields.Integer(readonly=True)
    month = fields.Integer(readonly=True)
    month_name = fields.Char(readonly=True)
    quarter = fields.Integer(readonly=True)
    week_of_year = fields.Integer(readonly=True)
    day_of_month = fields.Integer(readonly=True)
    day_of_week = fields.Integer(readonly=True)
    day_of_year = fields.Integer(readonly=True)


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
                    pt.categ_id AS product_categ_id,
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
        self._cr.execute(f"CREATE UNIQUE INDEX id_{table} ON {table} (line_id)")
