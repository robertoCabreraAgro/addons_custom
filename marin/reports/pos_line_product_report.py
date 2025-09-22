from psycopg2.extensions import AsIs

from odoo import fields, models


class PosLineProductReport(models.Model):
    _name = "pos.line.product.report"
    _description = "PoS Report by Product"
    _auto = False

    config_id = fields.Many2one(
        comodel_name="pos.config",
        string="Terminal",
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
    quarter = fields.Integer(
        readonly=True,
    )
    quarter_str = fields.Selection(
        selection=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")],
        readonly=True,
    )
    name = fields.Char(
        readonly=True,
    )
    total_qty = fields.Float(
        string="Cantidad venta tpv",
        readonly=True,
    )  # Field 1
    cost_purchase_total = fields.Float(
        readonly=True,
    )
    average_real_cost = fields.Float(
        string="Precio compra promedio tpv",
        readonly=True,
        aggregator="avg",
    )  # Field 2
    average_sale_price = fields.Float(
        string="Precio venta promedio tpv",
        readonly=True,
        aggregator="avg",
    )  # Field 3
    sale_price_total = fields.Float(
        string="Valor ventas tpv",
        readonly=True,
    )  # Field 4
    real_margin_value = fields.Float(
        string="Valor margen real",
        readonly=True,
    )  # Field 5

    def _query(self):
        return """
            WITH filtered_lines AS (
                SELECT
                    *
                FROM
                    pos_line_report
                WHERE
                    parent_state in ('paid', 'done', 'invoiced')
                    AND date >= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer), 1, 1)
                    AND date <= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer), 12, 31)
            ),
            grouped_lines AS (
                SELECT
                    config_id,
                    product_category_id,
                    product_id,
                    quarter,
                    CAST(quarter AS text) AS quarter_str,
                    SUM(quantity) AS total_qty,
                    SUM(price_subtotal) AS sale_price_total,
                    SUM(purchase_price_total) AS cost_purchase_total,
                    SUM(margin) AS real_margin_value
                FROM
                    filtered_lines
                GROUP BY
                    config_id,
                    product_category_id,
                    product_id,
                    quarter
            ),
            grouped_lines_computed AS (
                SELECT
                    *,
                    CASE
                        WHEN total_qty = 0 OR total_qty IS NULL THEN 0.0
                        ELSE cost_purchase_total / total_qty
                    END AS average_real_cost,
                    CASE
                        WHEN total_qty = 0 OR total_qty IS NULL THEN 0.0
                        ELSE sale_price_total / total_qty
                    END AS average_sale_price
                FROM
                    grouped_lines
            )
            SELECT
                row_number() OVER (ORDER BY config_id ASC, product_id ASC, quarter ASC) AS id,
                (row_number() OVER ())::VARCHAR AS str_id,
                *
            FROM
                grouped_lines_computed
            ORDER BY
                config_id ASC,
                product_id ASC,
                quarter ASC
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
            self._cr.execute(f"CREATE MATERIALIZED VIEW {table} AS ({query})")
        else:
            # To avoid long time to update the module we create the view without data
            # and later be populated by the cron that executes the method refresh()
            self._cr.execute(
                f"CREATE MATERIALIZED VIEW {table} AS ({query}) WITH NO DATA"
            )
        self._cr.execute(f"CREATE UNIQUE INDEX id_{table} ON {table} (id)")
