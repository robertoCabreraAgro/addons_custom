from psycopg2.extensions import AsIs

from odoo import fields, models


class InvoiceLineOutTeam(models.Model):
    _name = "invoice.line.out.team.report"
    _description = "Invoice Line Out by Team"
    _auto = False


    team_id = fields.Many2one("crm.team", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    commercial_partner_id = fields.Many2one("res.partner", readonly=True)
    product_id = fields.Many2one("product.product", readonly=True)
    product_categ_id = fields.Many2one("product.category", readonly=True)
    parent_categ_id = fields.Many2one("product.category", string="Parent Category", readonly=True)
    root_categ_id = fields.Many2one("product.category", string="Root Category", readonly=True)
    name = fields.Char(readonly=True)
    quarter = fields.Integer(readonly=True)
    total_qty_current_year = fields.Float("Cantidad venta real", readonly=True)  # Field 1
    total_qty_last_year = fields.Float(readonly=True)
    real_sale_variation_percentage = fields.Float("Variacion % cantidad venta real OYB", readonly=True, aggregator="avg")  # Field 2
    cost_purchase_total_current_year = fields.Float(readonly=True)
    cost_purchase_total_last_year = fields.Float(readonly=True)
    average_real_cost_current_year = fields.Float("Costo promedio real", readonly=True, aggregator="avg")  # Field 3
    average_real_cost_last_year = fields.Float(readonly=True, aggregator="avg")
    real_cost_variation_percentage = fields.Float("Variacion % costo promedio real OYB", readonly=True, aggregator="avg")  # Field 4
    average_abs_sale_price_current_year = fields.Float("Precio venta promedio real absoluto", readonly=True, aggregator="avg")  # Field 5
    average_abs_sale_price_last_year = fields.Float(readonly=True, aggregator="avg")
    average_sale_price_current_year = fields.Float("Precio venta promedio real", readonly=True, aggregator="avg")  # Field 6
    average_sale_price_last_year = fields.Float(readonly=True, aggregator="avg")
    real_price_variation_percentage = fields.Float(
        "Variacion % precio venta promedio real OYB", readonly=True, aggregator="avg"
    )  # Field 7
    sale_price_total_current_year = fields.Float("Valor ventas real", readonly=True)  # Field 8
    sale_price_total_last_year = fields.Float(readonly=True)
    sale_price_variation_percentage = fields.Float("Variacion % valor ventas real OYB", readonly=True, aggregator="avg")  # Field 9
    real_margin_value_current_year = fields.Float("Valor margen real", readonly=True)  # Field 10
    real_margin_value_last_year = fields.Float(readonly=True)
    real_margin_variation_percentage = fields.Float("Variacion % valor margen real OYB", readonly=True, aggregator="avg")  # Field 11

    real_sale_variation = fields.Float(readonly=True)
    real_cost_variation = fields.Float(readonly=True, aggregator="avg")
    real_price_variation = fields.Float(readonly=True, aggregator="avg")
    sale_price_variation = fields.Float(readonly=True)
    real_margin_variation = fields.Float(readonly=True)


    def _query(self):
        return """
            WITH filtered_lines AS (
                SELECT
                    *
                FROM
                    invoice_line_out_report
                WHERE
                    move_type = 'out_invoice'
                    AND x_treatment IN ('fiscal_real', 'not_fiscal_real')
                    AND company_id = 2
            ),
            filtered_lines_current_year AS (
                SELECT
                    *
                FROM
                    filtered_lines
                WHERE
                    date >= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer), 1, 1)
                    AND date <= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer), 12, 31)
            ),
            filtered_lines_last_year AS (
                SELECT
                    *
                FROM
                    filtered_lines
                WHERE
                    date >= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer) - 1, 1, 1)
                    AND date <= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer) - 1, 12, 31)
            ),
            grouped_lines_current_year AS (
                SELECT
                    team_id,
                    commercial_partner_id,
                    partner_id,
                    product_categ_id,
                    parent_categ_id,
                    root_categ_id,
                    product_id,
                    quarter,
                    SUM(quantity) AS total_qty_current_year,
                    SUM(price_subtotal) AS sale_price_total_current_year,
                    SUM(purchase_price_total) AS cost_purchase_total_current_year,
                    SUM(margin) AS real_margin_value_current_year
                FROM
                    filtered_lines_current_year
                GROUP BY
                    team_id,
                    commercial_partner_id,
                    partner_id,
                    product_categ_id,
                    parent_categ_id,
                    root_categ_id,
                    product_id,
                    quarter
            ),
            grouped_lines_last_year AS (
                SELECT
                    team_id,
                    commercial_partner_id,
                    partner_id,
                    product_categ_id,
                    parent_categ_id,
                    root_categ_id,
                    product_id,
                    quarter,
                    SUM(quantity) AS total_qty_last_year,
                    SUM(price_total) AS sale_price_total_last_year,
                    SUM(purchase_price_total) AS cost_purchase_total_last_year,
                    SUM(margin) AS real_margin_value_last_year
                FROM
                    filtered_lines_last_year
                GROUP BY
                    team_id,
                    commercial_partner_id,
                    partner_id,
                    product_categ_id,
                    parent_categ_id,
                    root_categ_id,
                    product_id,
                    quarter
            ),
            grouped_lines_current_year_computed AS (
                SELECT
                    *,
                    CASE
                        WHEN total_qty_current_year = 0 OR total_qty_current_year IS NULL THEN 0.0
                        ELSE cost_purchase_total_current_year / total_qty_current_year
                    END AS average_real_cost_current_year,
                    CASE
                        WHEN total_qty_current_year = 0 OR total_qty_current_year IS NULL THEN 0.0
                        ELSE sale_price_total_current_year / total_qty_current_year
                    END AS average_abs_sale_price_current_year,
                    CASE
                        WHEN total_qty_current_year = 0 OR total_qty_current_year IS NULL THEN 0.0
                        ELSE sale_price_total_current_year / total_qty_current_year
                    END AS average_sale_price_current_year
                FROM
                    grouped_lines_current_year
            ),
            grouped_lines_last_year_computed AS (
                SELECT
                    *,
                    CASE
                        WHEN total_qty_last_year = 0 OR total_qty_last_year IS NULL THEN 0.0
                        ELSE cost_purchase_total_last_year / total_qty_last_year
                    END AS average_real_cost_last_year,
                    CASE
                        WHEN total_qty_last_year = 0 OR total_qty_last_year IS NULL THEN 0.0
                        ELSE sale_price_total_last_year / total_qty_last_year
                    END AS average_abs_sale_price_last_year,
                    CASE
                        WHEN total_qty_last_year = 0 OR total_qty_last_year IS NULL THEN 0.0
                        ELSE sale_price_total_last_year / total_qty_last_year
                    END AS average_sale_price_last_year
                FROM
                    grouped_lines_last_year
            ),
            grouped_lines AS (
                SELECT
                    COALESCE(glcy.team_id, glly.team_id) AS team_id,
                    COALESCE(glcy.commercial_partner_id, glly.commercial_partner_id) AS commercial_partner_id,
                    COALESCE(glcy.partner_id, glly.partner_id) AS partner_id,
                    COALESCE(glcy.product_categ_id, glly.product_categ_id) AS product_categ_id,
                    COALESCE(glcy.parent_categ_id, glly.parent_categ_id) AS parent_categ_id,
                    COALESCE(glcy.root_categ_id, glly.root_categ_id) AS root_categ_id,
                    COALESCE(glcy.product_id, glly.product_id) AS product_id,
                    COALESCE(glcy.quarter, glly.quarter) AS quarter,
                    total_qty_current_year,  -- Field 1
                    total_qty_last_year,
                    sale_price_total_current_year,  -- Field 8
                    sale_price_total_last_year,
                    cost_purchase_total_current_year,
                    cost_purchase_total_last_year,
                    real_margin_value_current_year,  -- Field 10
                    real_margin_value_last_year,
                    average_real_cost_current_year,  -- Field 3
                    average_real_cost_last_year,
                    average_abs_sale_price_current_year,  -- Field 5
                    average_abs_sale_price_last_year,
                    average_sale_price_current_year,  -- Field 6
                    average_sale_price_last_year,

                    (COALESCE(total_qty_current_year, 0.0) - COALESCE(total_qty_last_year, 0.0)) AS real_sale_variation,
                    (COALESCE(average_real_cost_current_year, 0.0) - COALESCE(average_real_cost_last_year, 0.0)) AS real_cost_variation,
                    (COALESCE(average_abs_sale_price_current_year, 0.0) - COALESCE(average_abs_sale_price_last_year, 0.0)) AS real_price_variation,
                    (COALESCE(sale_price_total_current_year, 0.0) - COALESCE(sale_price_total_last_year, 0.0)) AS sale_price_variation,
                    (COALESCE(real_margin_value_current_year, 0.0) - COALESCE(real_margin_value_last_year, 0.0)) AS real_margin_variation,

                    -- Field 2
                    CASE
                        WHEN total_qty_last_year = 0 OR total_qty_last_year IS NULL THEN 0.0
                        ELSE (COALESCE(total_qty_current_year, 0.0) - total_qty_last_year) / total_qty_last_year * 100
                    END AS real_sale_variation_percentage,
                    -- Field 4
                    CASE
                        WHEN average_real_cost_last_year = 0 OR average_real_cost_last_year IS NULL THEN 0.0
                        ELSE (COALESCE(average_real_cost_current_year, 0.0) - average_real_cost_last_year) / average_real_cost_last_year * 100
                    END AS real_cost_variation_percentage,
                    -- Field 7
                    CASE
                        WHEN average_abs_sale_price_last_year = 0 OR average_abs_sale_price_last_year IS NULL THEN 0.0
                        ELSE (COALESCE(average_abs_sale_price_current_year, 0.0) - average_abs_sale_price_last_year) / average_abs_sale_price_last_year * 100
                    END AS real_price_variation_percentage,
                    -- Field 9
                    CASE
                        WHEN sale_price_total_last_year = 0 OR sale_price_total_last_year IS NULL THEN 0.0
                        ELSE (COALESCE(sale_price_total_current_year, 0.0) - sale_price_total_last_year) / sale_price_total_last_year * 100
                    END AS sale_price_variation_percentage,
                    -- Field 11
                    CASE
                        WHEN real_margin_value_last_year = 0 OR real_margin_value_last_year IS NULL THEN 0.0
                        ELSE (COALESCE(real_margin_value_current_year, 0.0) - real_margin_value_last_year) / real_margin_value_last_year * 100
                    END AS real_margin_variation_percentage
                FROM
                    grouped_lines_current_year_computed as glcy
                LEFT OUTER JOIN
                    grouped_lines_last_year_computed AS glly
                    ON glcy.team_id = glly.team_id
                    AND glcy.partner_id = glly.partner_id
                    AND glcy.product_id = glly.product_id
                    AND glcy.quarter = glly.quarter
            )
            SELECT
                row_number() OVER (ORDER BY gl.team_id ASC, gl.partner_id ASC, gl.product_id ASC, gl.quarter ASC) AS id,
                (row_number() OVER ())::VARCHAR AS str_id,
                gl.*,
                CONCAT(CAST(ct.name->>'en_US' AS text), ' - ', rp.name, ' - ', CAST(pt.name->>'en_US' AS text), ' - ', CAST(gl.quarter AS text)) AS name
            FROM
                grouped_lines AS gl
            INNER JOIN
                product_product AS pp
                ON pp.id = gl.product_id
            INNER JOIN
                product_template AS pt
                ON pt.id = pp.product_tmpl_id
            INNER JOIN
                res_partner AS rp
                ON rp.id = gl.partner_id
            INNER JOIN
                crm_team AS ct
                ON ct.id = gl.team_id
            ORDER BY
                gl.team_id ASC,
                gl.partner_id ASC,
                gl.product_id ASC,
                gl.quarter ASC
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
                f"CREATE MATERIALIZED VIEW {table} AS ({query})",
            )
        else:
            # To avoid long time to update the module we create the view without data
            # and later be populated by the cron that executes the method refresh_concurrently()
            self._cr.execute(
                f"CREATE MATERIALIZED VIEW {table} AS ({query}) WITH NO DATA",
            )
        self._cr.execute(f"CREATE UNIQUE INDEX id_{table} ON {table} (id)")
