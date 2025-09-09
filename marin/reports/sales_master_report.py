"""Sales Master Report - Consolidated sales analytics with invoice and POS data.

This report consolidates sales data from both invoices and POS orders,
providing comprehensive analytics including margins, collection tracking,
and year-over-year comparisons.
"""

from odoo import fields, models


class SalesMasterReport(models.Model):
    """Consolidated sales analytics report combining invoice and POS data.

    This report provides a unified view of sales performance across all channels,
    including detailed margin analysis, collection tracking, and comprehensive
    filtering capabilities for business intelligence.
    """

    _name = "sales.master.report"
    _description = "Sales Master Report - Consolidated Analytics"
    _auto = False
    _order = "invoice_date DESC, user_id, partner_id"
    _rec_name = "display_name"

    # =====================
    # CORE DIMENSIONS
    # =====================
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
        help="Company that generated the transaction",
    )
    move_id = fields.Many2one(
        "account.move",
        string="Invoice/Bill",
        readonly=True,
        help="Related accounting entry (null for POS transactions)",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        readonly=True,
        help="User responsible for the sale",
    )
    team_id = fields.Many2one(
        "crm.team",
        string="Sales Team",
        readonly=True,
        help="Sales team assigned to the transaction",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        readonly=True,
        help="Customer who made the purchase",
    )
    commercial_partner_id = fields.Many2one(
        "res.partner",
        string="Commercial Entity",
        readonly=True,
        help="Main commercial partner (parent company)",
    )

    # Product Dimensions
    product_id = fields.Many2one(
        "product.product",
        string="Product Variant",
        readonly=True,
        help="Specific product variant sold",
    )
    product_category_id = fields.Many2one(
        "product.category",
        string="Product Category",
        readonly=True,
        help="Direct product category",
    )
    parent_categ_id = fields.Many2one(
        "product.category",
        string="Parent Category",
        readonly=True,
        help="Parent level category for grouping",
    )
    root_categ_id = fields.Many2one(
        "product.category",
        string="Root Category",
        readonly=True,
        help="Top-level category classification",
    )
    manufacturer_id = fields.Many2one(
        "res.partner", string="Manufacturer", readonly=True, help="Product manufacturer"
    )

    # =====================
    # TEMPORAL FIELDS
    # =====================
    invoice_date = fields.Date(
        string="Transaction Date",
        readonly=True,
        help="Date when the sale transaction occurred",
    )

    # =====================
    # CORE SALES METRICS
    # =====================
    quantity = fields.Float(
        string="Quantity Sold", readonly=True, help="Total quantity of products sold"
    )
    sale_price_total = fields.Float(
        string="Total Sale Value",
        readonly=True,
        help="Total revenue from the sale (tax included for POS)",
    )
    purchase_price = fields.Float(
        string="Avg Purchase Price",
        readonly=True,
        aggregator="avg",
        help="Weighted average purchase price per unit",
    )
    cost_purchase_total = fields.Float(
        string="Total Purchase Cost", readonly=True, help="Total cost of goods sold"
    )

    # =====================
    # CLASSIFICATION FIELDS
    # =====================
    x_treatment = fields.Selection(
        selection=[
            ("not_fiscal_simulated", "Not Fiscal Simulated"),
            ("not_fiscal_real", "Not Fiscal Real"),
            ("fiscal_simulated", "Fiscal Simulated"),
            ("fiscal_real", "Fiscal Real"),
        ],
        string="Fiscal Treatment",
        readonly=True,
        help="Type of fiscal treatment applied to the transaction",
    )
    sale_channel = fields.Selection(
        selection=[
            ("invoice", "Invoice/Bill"),
            ("pos", "Point of Sale"),
        ],
        string="Sales Channel",
        readonly=True,
        help="Channel through which the sale was made",
    )
    payment_state = fields.Selection(
        selection=[
            ("not_paid", "Not Paid"),
            ("in_payment", "In Payment"),
            ("paid", "Paid"),
            ("partial", "Partially Paid"),
            ("reversed", "Reversed"),
            ("invoicing_legacy", "Legacy"),
        ],
        string="Payment Status",
        readonly=True,
        help="Current payment status of the transaction",
    )

    # =====================
    # PRICING & PROFITABILITY
    # =====================
    price_unit = fields.Float(
        string="Avg Unit Price",
        readonly=True,
        aggregator="avg",
        help="Average selling price per unit",
    )
    discount = fields.Float(
        string="Avg Discount %",
        readonly=True,
        aggregator="avg",
        help="Average discount percentage applied",
    )
    margin = fields.Float(
        string="Total Margin",
        readonly=True,
        help="Total profit margin (sale price - cost)",
    )
    margin_percent = fields.Float(
        string="Margin %",
        readonly=True,
        aggregator="avg",
        help="Margin percentage (calculated in query)",
    )

    # =====================
    # COLLECTION MANAGEMENT
    # =====================
    invoice_amount_total = fields.Float(
        string="Invoice Total", readonly=True, help="Total amount invoiced"
    )
    amount_paid = fields.Float(
        string="Amount Paid", readonly=True, help="Amount actually paid by customer"
    )
    amount_due = fields.Float(
        string="Amount Due", readonly=True, help="Outstanding amount pending collection"
    )
    collection_percentage = fields.Float(
        string="Collection %",
        readonly=True,
        aggregator="avg",
        help="Percentage of invoice amount collected",
    )
    collected_price_total = fields.Float(
        string="Revenue Collected",
        readonly=True,
        help="Proportional revenue based on collection rate",
    )
    collected_margin = fields.Float(
        string="Margin Collected",
        readonly=True,
        help="Proportional margin based on collection rate",
    )

    # =====================
    # COMPUTED FIELDS
    # =====================
    display_name = fields.Char(
        string="Description",
        compute="_compute_display_name",
        help="Human-readable description of the sales record",
    )

    def _compute_display_name(self):
        """Compute human-readable display name for sales records.

        Creates a descriptive name combining product and customer information
        for easy identification in lists and reports.
        """
        for record in self:
            parts = []

            if record.product_id:
                parts.append(record.product_id.name)

            if record.partner_id:
                parts.append(f"sold to {record.partner_id.name}")

            if record.user_id:
                parts.append(f"by {record.user_id.name}")

            if parts:
                record.display_name = " ".join(parts)
            else:
                record.display_name = f"Sales Record #{record.id}"

    @property
    def _table_query(self):
        """Return the SQL query that defines this reporting table.

        This property is required by Odoo for SQL view models (_auto=False).
        It returns the complete SQL query that creates the virtual table.

        Returns:
            str: Complete SQL query for the sales master report
        """
        return self._query()

    def _query(self):
        """Build the main SQL query for the sales master report.

        This method constructs a comprehensive SQL query that combines invoice
        and POS data, providing unified sales analytics. The query uses CTEs
        (Common Table Expressions) for better readability and performance.

        Returns:
            str: Complete SQL query with CTEs for data aggregation
        """
        return f"""
            WITH
            -- Aggregate invoice line data with collection tracking
            invoice_data AS (
                {self._select_invoice_aggregated()}
                FROM {self._from_sales()}
                WHERE {self._where_sales()}
                GROUP BY {self._group_by_sales()}
            ),
            -- Aggregate POS data (always fully paid)
            pos_data AS (
                {self._select_pos_aggregated()}
                FROM {self._from_pos()}
                WHERE {self._where_pos()}
                GROUP BY {self._group_by_pos()}
            ),
            -- Combine both data sources
            combined_data AS (
                SELECT * FROM invoice_data
                UNION ALL
                SELECT * FROM pos_data
            )
            -- Final result set with calculated fields
            SELECT 
                ROW_NUMBER() OVER (
                    ORDER BY invoice_date DESC, user_id, partner_id, product_id
                ) AS id,
                
                -- Core dimensions
                move_id,
                company_id,
                user_id,
                team_id, 
                partner_id,
                commercial_partner_id,
                product_id,
                product_category_id,
                parent_categ_id,
                root_categ_id,
                manufacturer_id,
                
                -- Temporal and classification
                invoice_date,
                x_treatment,
                sale_channel,
                payment_state,

                -- Core metrics
                quantity,
                sale_price_total,
                purchase_price,
                cost_purchase_total,
                price_unit,
                discount,
                margin,
                
                -- Calculated percentages
                CASE WHEN sale_price_total > 0 
                     THEN ROUND((margin / sale_price_total) * 100.0, 2)
                     ELSE 0 
                END AS margin_percent,

                -- Collection management
                invoice_amount_total,
                amount_paid,
                amount_due,
                CASE WHEN invoice_amount_total > 0 
                     THEN ROUND((amount_paid / invoice_amount_total) * 100.0, 2)
                     ELSE 0 
                END AS collection_percentage,
                collected_price_total,
                collected_margin

            FROM combined_data
        """

    def _select_invoice_aggregated(self):
        """Select and aggregate invoice line data.

        Aggregates accounting move lines with proper cost calculation,
        collection tracking based on payment status, and margin analysis.

        Returns:
            str: SQL SELECT clause for invoice data aggregation
        """
        # Helper for cost calculation with fallback
        cost_calculation = """
            COALESCE(
                aml.purchase_price, 
                COALESCE(
                    CAST(pp.standard_price->>move.company_id::text AS NUMERIC), 
                    0
                )
            )
        """

        # Collection rate calculation
        collection_rate = """
            CASE WHEN move.amount_total > 0 
                THEN (move.amount_total - COALESCE(move.amount_residual, move.amount_total)) / move.amount_total
                ELSE 0 
            END
        """

        return f"""
            SELECT
                -- Primary keys and dimensions
                move.id AS move_id,
                move.company_id,
                move.invoice_user_id AS user_id,
                move.team_id,
                move.partner_id,
                move.commercial_partner_id,
                aml.product_id,
                pc.id AS product_category_id,
                CASE
                    WHEN pc.parent_id = pc.root_categ_id THEN pc.id
                    ELSE pc.parent_id
                END AS parent_categ_id,
                pc.root_categ_id,
                pt.manufacturer_id,
                
                -- Temporal and classification
                move.invoice_date,
                journal.x_treatment,
                'invoice'::text AS sale_channel,
                move.payment_state,

                -- Aggregated quantities and amounts
                SUM(aml.quantity) AS quantity,
                SUM(aml.price_total) AS sale_price_total,

                -- Weighted average purchase price
                CASE 
                    WHEN SUM(aml.quantity) > 0 
                    THEN SUM(({cost_calculation}) * aml.quantity) / SUM(aml.quantity)
                    ELSE 0 
                END AS purchase_price,

                -- Total costs
                SUM(({cost_calculation}) * aml.quantity) AS cost_purchase_total,

                -- Pricing averages
                AVG(aml.price_unit) AS price_unit,
                AVG(COALESCE(aml.discount, 0)) AS discount,

                -- Margin calculation
                SUM(
                    aml.price_total - (({cost_calculation}) * aml.quantity)
                ) AS margin,
                0 AS margin_percent,  -- Calculated in main query

                -- Collection Management
                SUM(aml.price_total) AS invoice_amount_total,
                SUM(aml.price_total * COALESCE(({collection_rate}), 0)) AS amount_paid,
                SUM(aml.price_total * COALESCE(
                    CASE WHEN move.amount_total > 0 
                        THEN COALESCE(move.amount_residual, move.amount_total) / move.amount_total
                        ELSE 1 
                    END, 1
                )) AS amount_due,
                SUM(aml.price_total * COALESCE(({collection_rate}), 0)) AS collected_price_total,
                SUM(
                    (aml.price_total - (({cost_calculation}) * aml.quantity)) * 
                    COALESCE(({collection_rate}), 0)
                ) AS collected_margin
        """

    def _from_sales(self):
        """Define table joins for invoice data.

        Creates proper relationships between accounting moves, products,
        partners, and organizational structures.

        Returns:
            str: SQL FROM clause with all necessary joins
        """
        return """
            account_move_line aml
            INNER JOIN account_move move ON aml.move_id = move.id
            INNER JOIN account_journal journal ON move.journal_id = journal.id
            LEFT JOIN crm_team team ON move.team_id = team.id
            INNER JOIN res_partner partner ON move.partner_id = partner.id
            INNER JOIN product_product pp ON aml.product_id = pp.id
            INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
            INNER JOIN product_category pc ON pt.categ_id = pc.id
        """

    def _where_sales(self):
        """Define filtering conditions for invoice data.

        Filters for validated customer transactions with real fiscal treatment
        and excludes non-product lines (sections, notes, etc.).

        Returns:
            str: SQL WHERE clause with filtering conditions
        """
        return """
            move.move_type IN ('out_invoice', 'out_refund')
            AND move.state = 'posted'
            AND journal.x_treatment IN ('fiscal_real', 'not_fiscal_real')
            AND aml.display_type = 'product'
            AND aml.product_id IS NOT NULL
            AND aml.quantity != 0
        """

    def _group_by_sales(self):
        """Define grouping for invoice data aggregation.

        Groups by all non-aggregated fields to ensure proper
        data summarization by transaction and product.

        Returns:
            str: SQL GROUP BY clause
        """
        return """
            move.id,
            move.company_id,
            move.invoice_user_id,
            move.team_id,
            move.partner_id,
            move.commercial_partner_id,
            aml.product_id,
            pc.id,
            pc.parent_id,
            pc.root_categ_id,
            pt.manufacturer_id,
            move.invoice_date,
            journal.x_treatment,
            move.payment_state
        """

    def _select_pos_aggregated(self):
        """Select and aggregate POS order data.

        Aggregates Point of Sale transactions which are always fully paid.
        Uses standard_price for cost calculation as POS doesn't track purchase_price.

        Returns:
            str: SQL SELECT clause for POS data aggregation
        """
        # Standard cost calculation for POS
        pos_cost_calc = """
            COALESCE(
                CAST(pp.standard_price->>pos_order.company_id::text AS NUMERIC), 
                0
            )
        """

        return f"""
            SELECT
                -- POS transactions don't have move_id
                NULL::integer AS move_id,
                pos_order.company_id,
                pos_order.user_id,
                pos_order.crm_team_id AS team_id,
                COALESCE(pos_order.partner_id, 1) AS partner_id,  -- Default to generic customer
                COALESCE(pos_order.partner_id, 1) AS commercial_partner_id,
                pol.product_id,
                pc.id AS product_category_id,
                CASE
                    WHEN pc.parent_id = pc.root_categ_id THEN pc.id
                    ELSE pc.parent_id
                END AS parent_categ_id,
                pc.root_categ_id,
                pt.manufacturer_id,
                
                -- Temporal and classification
                pos_order.date_order AS invoice_date,
                'fiscal_real'::text AS x_treatment,
                'pos'::text AS sale_channel,
                'paid'::text AS payment_state,  -- POS is always paid

                -- Aggregated quantities and amounts
                SUM(pol.qty) AS quantity,
                SUM(pol.price_subtotal_incl) AS sale_price_total,
                
                -- Weighted average cost (using standard_price)
                CASE WHEN SUM(pol.qty) > 0 
                    THEN SUM(pol.qty * ({pos_cost_calc})) / SUM(pol.qty)
                    ELSE 0 
                END AS purchase_price,
                SUM(pol.qty * ({pos_cost_calc})) AS cost_purchase_total,

                -- Pricing averages
                AVG(pol.price_unit) AS price_unit,
                AVG(COALESCE(pol.discount, 0)) AS discount,
                
                -- Margin calculation
                SUM(pol.price_subtotal_incl - (pol.qty * ({pos_cost_calc}))) AS margin,
                0 AS margin_percent,  -- Calculated in main query

                -- Collection (POS is always fully collected)
                SUM(pol.price_subtotal_incl) AS invoice_amount_total,
                SUM(pol.price_subtotal_incl) AS amount_paid,
                0::numeric AS amount_due,
                SUM(pol.price_subtotal_incl) AS collected_price_total,
                SUM(pol.price_subtotal_incl - (pol.qty * ({pos_cost_calc}))) AS collected_margin
        """

    def _from_pos(self):
        """Define table joins for POS data.

        Creates relationships between POS orders, products,
        and product categories.

        Returns:
            str: SQL FROM clause for POS data
        """
        return """
            pos_order_line pol
            INNER JOIN pos_order ON pol.order_id = pos_order.id
            INNER JOIN product_product pp ON pol.product_id = pp.id
            INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
            INNER JOIN product_category pc ON pt.categ_id = pc.id
        """

    def _where_pos(self):
        """Define filtering conditions for POS data.

        Filters for completed POS transactions with valid products
        and positive quantities.

        Returns:
            str: SQL WHERE clause for POS filtering
        """
        return """
            pos_order.state IN ('paid', 'done', 'invoiced')
            AND pol.product_id IS NOT NULL
            AND pol.qty > 0
            AND pos_order.date_order IS NOT NULL
        """

    def _group_by_pos(self):
        """Define grouping for POS data aggregation.

        Groups by all non-aggregated fields to ensure proper
        data summarization by POS order and product.

        Returns:
            str: SQL GROUP BY clause for POS data
        """
        return """
            pos_order.company_id,
            pos_order.user_id,
            pos_order.crm_team_id,
            pos_order.partner_id,
            pol.product_id,
            pc.id,
            pc.parent_id,
            pc.root_categ_id,
            pt.manufacturer_id,
            pos_order.date_order
        """
