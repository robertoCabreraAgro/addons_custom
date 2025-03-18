from psycopg2.extensions import AsIs

from odoo import fields, models


class StockNeed(models.Model):
    _name = "stock.need.report"
    _description = "Stock Need"
    _auto = False
    _order = "root_categ_id ASC, product_categ_id ASC, product_id ASC"

    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    product_categ_id = fields.Many2one(
        "product.category", string="Product Category", readonly=True
    )
    parent_categ_id = fields.Many2one(
        "product.category", string="Parent Category", readonly=True
    )
    root_categ_id = fields.Many2one(
        "product.category", string="Root Category", readonly=True
    )
    name = fields.Char(readonly=True)
    available_quantity = fields.Float("Stock available Qty", readonly=True)
    quantity = fields.Float("Stock on hand Qty", readonly=True)
    standard_price = fields.Float("Product standar price", readonly=True)
    available_stock_cost_value = fields.Float(
        "Suma de Valor stock disponible a costo", readonly=True
    )
    available_stock_price_value = fields.Float(
        "Suma de Valor stock disponible a precio de lista", readonly=True
    )
    last_year_qty_sold = fields.Float(
        "Cantidad venta real año pasado LMMR", readonly=True
    )
    current_year_qty_sold = fields.Float(
        "Cantidad venta real año actual LMMR", readonly=True
    )
    stock_supply_need = fields.Float(
        "Stock supply need qty año actual LMMR", readonly=True
    )
    stock_supply_need_value = fields.Float(
        "Stock supply need value at standard price año actual LMMR", readonly=True
    )

    def _query(self):
        return """
            WITH root_categories AS (
                SELECT
                    res_id
                FROM
                    ir_model_data
                WHERE
                    name IN (
                        'product_category_105',
                        'product_category_104'
                    )
                    AND module = 'marin'
            ),
            products AS (
                SELECT
                    pp.id AS id,
                    pt.name,
                    COALESCE(CAST(pp.standard_price->>'2' AS float), 0.0) AS standard_price,
                    pt.list_price,
                    pt.uom_id,
                    pt.categ_id,
                    CASE
                        WHEN pc.parent_id = pc.root_categ_id THEN pc.id
                        ELSE pc.parent_id
                    END AS parent_categ_id,
                    pc.root_categ_id
                FROM
                    product_product AS pp
                INNER JOIN
                    product_template AS pt
                    ON pt.id = pp.product_tmpl_id
                INNER JOIN
                    product_category AS pc
                    ON pc.id = pt.categ_id
                INNER JOIN
                    root_categories AS rc
                    ON rc.res_id = pc.root_categ_id
            ),
            locations AS (
                SELECT
                    id
                FROM
                    stock_location
                WHERE
                    usage = 'internal'
            ),
            move_line_quantities AS (
                SELECT
                    aml.id,
                    aml.product_id,
                    aml.move_type,
                    aml.date,
                    convert_uom(aml.product_id, aml.quantity, aml.product_uom_id, prod.uom_id) AS quantity,
                    aml.price_subtotal
                FROM
                    account_move_line AS aml
                INNER JOIN
                    products AS prod
                    ON prod.id = aml.product_id
                INNER JOIN
                    account_journal AS aj
                    ON aj.id = aml.journal_id
                WHERE
                    aml.display_type = 'product'
                    AND aml.move_type IN ('out_invoice', 'out_refund')
                    AND aml.date >= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer) - 1, 1, 1)
                    AND aml.date <= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer), 12, 31)
                    AND aml.company_id = 2
                    AND aml.product_id IS NOT NULL
                    AND aml.quantity IS NOT NULL
                    AND aml.product_uom_id IS NOT NULL
                    AND prod.uom_id IS NOT NULL
                    AND aj.x_treatment IN ('fiscal_real', 'not_fiscal_real')
            ),
            amls_out_current_year AS (
                SELECT
                    product_id,
                    SUM(quantity) AS quantity,
                    SUM(price_subtotal) AS price_subtotal
                FROM
                    move_line_quantities
                WHERE
                    move_type = 'out_invoice'
                    AND date >= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer), 1, 1)
                GROUP BY
                    product_id
            ),
            amls_refund_current_year AS (
                SELECT
                    product_id,
                    SUM(quantity) AS quantity,
                    SUM(price_subtotal) AS price_subtotal
                FROM
                    move_line_quantities
                WHERE
                    move_type = 'out_refund'
                    AND date >= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer), 1, 1)
                GROUP BY
                    product_id
            ),
            amls_out_last_year AS (
                SELECT
                    product_id,
                    SUM(quantity) AS quantity,
                    SUM(price_subtotal) AS price_subtotal
                FROM
                    move_line_quantities
                WHERE
                    move_type = 'out_invoice'
                    AND date <= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer) - 1, 12, 31)
                GROUP BY
                    product_id
            ),
            amls_refund_last_year AS (
                SELECT
                    product_id,
                    SUM(quantity) AS quantity,
                    SUM(price_subtotal) AS price_subtotal
                FROM
                    move_line_quantities
                WHERE
                    move_type = 'out_refund'
                    AND date <= MAKE_DATE(CAST(EXTRACT(YEAR FROM now()) AS integer) - 1, 12, 31)
                GROUP BY
                    product_id
            ),
            quants AS (
                SELECT 
                    sq.product_id,
                    SUM(sq.quantity) AS quantity,
                    SUM(sq.reserved_quantity) AS reserved_quantity
                FROM 
                    stock_quant AS sq
                INNER JOIN
                    locations AS sl
                    ON sl.id = sq.location_id
                WHERE 
                    sq.company_id = 2
                GROUP BY
                    sq.product_id
            )
            SELECT
                pp.id AS id,
                pp.id AS product_id,
                pp.name,
                pp.categ_id AS product_categ_id,
                pp.parent_categ_id,
                pp.root_categ_id,
                COALESCE(sq.quantity, 0.0) - COALESCE(sq.reserved_quantity, 0.0) AS available_quantity, -- Field 1
                COALESCE(sq.quantity, 0.0) AS quantity,  -- Field 2
                COALESCE(sq.reserved_quantity, 0.0) AS reserved_quantity,
                pp.standard_price,  -- Field 3
                pp.list_price,
                (
                    COALESCE(sq.quantity, 0.0) - COALESCE(sq.reserved_quantity, 0.0)
                ) * pp.standard_price AS available_stock_cost_value,  -- Field 4
                (
                    COALESCE(sq.quantity, 0.0) - COALESCE(sq.reserved_quantity, 0.0)
                ) * pp.list_price AS available_stock_price_value,  -- Field 5
                COALESCE(aoly.quantity, 0.0) - COALESCE(arly.quantity, 0.0) AS last_year_qty_sold,  -- Field 6
                COALESCE(aoly.price_subtotal, 0.0) - COALESCE(arly.price_subtotal, 0.0) AS last_year_amount_sold,
                COALESCE(aocy.quantity, 0.0) - COALESCE(arcy.quantity, 0.0) AS current_year_qty_sold,  -- Field 7
                COALESCE(aocy.price_subtotal, 0.0) - COALESCE(arcy.price_subtotal, 0.0) AS current_year_amount_sold,
                
                ((COALESCE(aoly.quantity, 0.0) - COALESCE(arly.quantity, 0.0))
                    - (COALESCE(aocy.quantity, 0.0) - COALESCE(arcy.quantity, 0.0))
                    - COALESCE(sq.quantity, 0.0)
                ) AS stock_supply_need,  -- Field 8
                ((COALESCE(aoly.quantity, 0.0) - COALESCE(arly.quantity, 0.0)
                    - (COALESCE(aocy.quantity, 0.0) - COALESCE(arcy.quantity, 0.0))
                    - COALESCE(sq.quantity, 0.0)
                ) * pp.standard_price) AS stock_supply_need_value  -- Field 9
            FROM
                products AS pp
            LEFT OUTER JOIN
                quants AS sq
                ON pp.id = sq.product_id
            LEFT OUTER JOIN
                amls_out_current_year AS aocy
                ON pp.id = aocy.product_id
            LEFT OUTER JOIN
                amls_refund_current_year AS arcy
                ON pp.id = arcy.product_id
            LEFT OUTER JOIN
                amls_out_last_year AS aoly
                ON pp.id = aoly.product_id
            LEFT OUTER JOIN
                amls_refund_last_year AS arly
                ON pp.id = arly.product_id
        """

    def refresh_concurrently(self):
        table = AsIs(self._table)
        if not self._check_populated(table):
            self._cr.execute("REFRESH MATERIALIZED VIEW %s" % (table,))
            return
        self._cr.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY %s", (table,))

    def _check_populated(self, table):
        self._cr.execute(
            "SELECT relispopulated FROM pg_class WHERE relname = '%s' and relkind = 'm'"
            % (table,)
        )
        res = self._cr.fetchone()
        return res and res[0]

    def init(self):
        table = AsIs(self._table)
        query = AsIs(self._query())
        self.create_function_convert_uom()
        self._cr.execute("DROP MATERIALIZED view IF EXISTS %s CASCADE", (table,))
        if self._context.get("with_data"):
            # When calling with that context it will create the view and populate it
            self._cr.execute(
                "CREATE MATERIALIZED VIEW %s AS (%s)",
                (
                    table,
                    query,
                ),
            )
        else:
            # To avoid long time to update the module we create the view without data
            # and later be populated by the cron that executes the method refresh_concurrently()
            self._cr.execute(
                "CREATE MATERIALIZED VIEW %s AS (%s) WITH NO DATA",
                (
                    table,
                    query,
                ),
            )
        self._cr.execute("CREATE UNIQUE INDEX id_%s ON %s(product_id)", (table, table))

    def create_function_convert_uom(self):
        self._cr.execute(
            """
            CREATE OR REPLACE FUNCTION convert_uom(
                prod int, qty float, from_uom_id int, to_uom_id int)
            RETURNS float AS $e_name$
            DECLARE
                con_factor float;
            BEGIN
                IF from_uom_id = to_uom_id OR qty = 0.0 THEN
                    return qty;
                END IF;

                WITH to_uom AS (
                    SELECT
                        u.factor
                    FROM
                        uom_uom AS u
                    INNER JOIN
                        uom_category AS uc
                        ON uc.id = u.category_id
                    INNER JOIN
                        uom_uom AS u_on_p
                        ON uc.id = u_on_p.category_id -- Category from the same as Category to
                    INNER JOIN
                        product_template AS pt
                        ON pt.uom_id = u_on_p.id -- in the template
                    INNER JOIN
                        product_product AS pp
                        ON (pp.product_tmpl_id = pt.id AND pp.id = prod) -- in the product
                    WHERE
                        u.id = to_uom_id
                ),
                from_uom AS (
                    SELECT
                        u.factor
                    FROM
                        uom_uom AS u
                    INNER JOIN
                        uom_category AS uc
                        ON uc.id = u.category_id
                    INNER JOIN
                        uom_uom AS u_on_p
                        ON uc.id = u_on_p.category_id -- Category from the same as Category to
                    INNER JOIN
                        product_template AS pt
                        ON pt.uom_id = u_on_p.id -- in the template
                    INNER JOIN
                        product_product AS pp
                        ON (pp.product_tmpl_id = pt.id AND pp.id = prod) -- in the product
                    WHERE
                        u.id = from_uom_id
                )
                SELECT qty / (SELECT factor FROM from_uom) * (SELECT factor FROM to_uom) INTO con_factor;
                return con_factor;
            END;
            $e_name$ LANGUAGE plpgsql;
        """
        )
