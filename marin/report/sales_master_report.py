from odoo import fields, models

class SalesMasterReport(models.Model):
    """Sales Master Report"""
    
    _name = "sales.master.report"
    _description = "Sales Master Report"
    _auto = False
    _order = "invoice_date DESC"
    _rec_name = "id"
    
    # Core dimensions
    move_id = fields.Many2one("account.move", string="Entry", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    team_id = fields.Many2one("crm.team", string="Sales Team", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Partner", readonly=True)
    commercial_partner_id = fields.Many2one("res.partner", string="Commercial Partner", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    product_category_id = fields.Many2one("product.category", string="Product Category", readonly=True)
    parent_categ_id = fields.Many2one("product.category", string="Parent Category", readonly=True)
    root_categ_id = fields.Many2one("product.category", string="Root Category", readonly=True)
    
    # Temporal fields
    invoice_date = fields.Date(string="Invoice Date", readonly=True)
    
    # Core metrics
    quantity = fields.Float(string="Quantity", readonly=True)
    sale_price_total = fields.Float(string="Sale Price Total", readonly=True)
    purchase_price = fields.Float(string="Purchase Price", readonly=True, aggregator="avg")
    cost_purchase_total = fields.Float(string="Cost Purchase Total", readonly=True)
    
    # Technical fields
    x_treatment = fields.Selection([
        ("not_fiscal_simulated", "Not Fiscal Simulated"),
        ("not_fiscal_real", "Not Fiscal Real"),
        ("fiscal_simulated", "Fiscal Simulated"),
        ("fiscal_real", "Fiscal Real"),
    ], string="Treatment", readonly=True)
    sale_channel = fields.Selection([
        ('invoice', 'Invoice'),
        ('pos', 'POS'),
    ], string="Sale Channel", readonly=True)
    
    # Pricing and profitability fields
    price_unit = fields.Float(string="Unit Price", readonly=True, aggregator="avg")
    discount = fields.Float(string="Average Discount %", readonly=True, aggregator="avg")
    margin = fields.Float(string="Total Margin Amount", readonly=True)
    margin_percent = fields.Float(string="Average Margin %", readonly=True, aggregator="avg")
    
    # Collection Management Fields
    invoice_amount_total = fields.Float(string="Invoice Total", readonly=True)
    amount_paid = fields.Float(string="Amount Paid", readonly=True)
    amount_due = fields.Float(string="Amount Due", readonly=True)
    collection_percentage = fields.Float(string="Collection %", readonly=True, aggregator="avg")
    collected_price_total = fields.Float(string="Amount Actually Collected", readonly=True)
    collected_margin = fields.Float(string="Margin Actually Collected", readonly=True)
    
    # Operational fields
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
    ], string="Payment Status", readonly=True)
    
    # Analysis fields
    manufacturer_id = fields.Many2one("res.partner", string="Manufacturer", readonly=True)
    
    def _compute_display_name(self):
        """Compute display name for sales master report records."""
        for record in self:
            if record.product_id and record.partner_id:
                record.display_name = f"{record.product_id.name} - {record.partner_id.name}"
            elif record.product_id:
                record.display_name = record.product_id.name
            elif record.partner_id:
                record.display_name = record.partner_id.name
            else:
                record.display_name = f"Sales Record #{record.id}"
    
    @property
    def _table_query(self):
        """Return the SQL query for the table."""
        return self._query()

    def _query(self):
        """Build query with pure group aggregations."""
        return f"""
            WITH invoice_data AS (
                {self._select_invoice_aggregated()}
                FROM {self._from_sales()}
                WHERE {self._where_sales()}
                GROUP BY {self._group_by_sales()}
            ),
            pos_data AS (
                {self._select_pos_aggregated()}
                FROM {self._from_pos()}
                WHERE {self._where_pos()}
                GROUP BY {self._group_by_pos()}
            ),
            combined_data AS (
                SELECT * FROM invoice_data
                UNION ALL
                SELECT * FROM pos_data
            )
            SELECT 
                ROW_NUMBER() OVER (ORDER BY user_id, team_id, partner_id, product_id, invoice_date) AS id,
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
                invoice_date,
                x_treatment,
                sale_channel,
                
                quantity,
                sale_price_total,
                purchase_price,
                cost_purchase_total,
                
                price_unit,
                discount,
                margin,
                CASE WHEN sale_price_total > 0 
                     THEN (margin / sale_price_total) * 100.0
                     ELSE 0 END AS margin_percent,
                
                invoice_amount_total,
                amount_paid,
                amount_due,
                CASE WHEN invoice_amount_total > 0 
                     THEN (amount_paid / invoice_amount_total) * 100.0
                     ELSE 0 END AS collection_percentage,
                collected_price_total,
                collected_margin,
                
                payment_state,
                manufacturer_id
                     
            FROM combined_data
        """

    def _select_invoice_aggregated(self):
        return """
            SELECT
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
                move.invoice_date,
                journal.x_treatment,
                'invoice'::text AS sale_channel,
                
                SUM(aml.quantity) AS quantity,
                SUM(aml.price_total) AS sale_price_total,
                
                -- Weighted average purchase price (with fallback to standard_price)
                CASE 
                    WHEN SUM(aml.quantity) > 0 
                    THEN SUM(
                        COALESCE(
                            aml.purchase_price, 
                            COALESCE(
                                CAST(pp.standard_price->>move.company_id::text AS NUMERIC), 
                                0
                            )
                        ) * aml.quantity
                    ) / SUM(aml.quantity)
                    ELSE 0 
                END AS purchase_price,
                
                SUM(
                    COALESCE(
                        aml.purchase_price, 
                        COALESCE(
                            CAST(pp.standard_price->>move.company_id::text AS NUMERIC), 
                            0
                        )
                    ) * aml.quantity
                ) AS cost_purchase_total,
                
                AVG(aml.price_unit) AS price_unit,
                AVG(COALESCE(aml.discount, 0)) AS discount,
                
                SUM(
                    aml.price_total - 
                    COALESCE(
                        aml.purchase_price, 
                        COALESCE(
                            CAST(pp.standard_price->>move.company_id::text AS NUMERIC), 
                            0
                        )
                    ) * aml.quantity
                ) AS margin,
                0 AS margin_percent,
                
                -- Collection Management Fields
                SUM(aml.price_total) AS invoice_amount_total,
                
                SUM(aml.price_total * COALESCE(
                    CASE WHEN move.amount_total > 0 
                        THEN (move.amount_total - COALESCE(move.amount_residual, move.amount_total)) / move.amount_total
                        ELSE 0 END, 0
                )) AS amount_paid,
                
                SUM(aml.price_total * COALESCE(
                    CASE WHEN move.amount_total > 0 
                        THEN COALESCE(move.amount_residual, move.amount_total) / move.amount_total
                        ELSE 1 END, 1
                )) AS amount_due,
                
                SUM(aml.price_total * COALESCE(
                    CASE WHEN move.amount_total > 0 
                        THEN (move.amount_total - COALESCE(move.amount_residual, move.amount_total)) / move.amount_total
                        ELSE 0 END, 0
                )) AS collected_price_total,
                
                SUM((aml.price_total - COALESCE(aml.purchase_price, COALESCE(CAST(pp.standard_price->>move.company_id::text AS NUMERIC), 0)) * aml.quantity) * COALESCE(
                    CASE WHEN move.amount_total > 0 
                        THEN (move.amount_total - COALESCE(move.amount_residual, move.amount_total)) / move.amount_total
                        ELSE 0 END, 0
                )) AS collected_margin,
                
                move.payment_state,
                pt.manufacturer_id
        """

    def _from_sales(self):
        return """
            account_move_line aml
            INNER JOIN account_move move ON aml.move_id = move.id
            INNER JOIN account_journal journal ON move.journal_id = journal.id
            INNER JOIN crm_team team ON move.team_id = team.id
            INNER JOIN res_partner partner ON move.partner_id = partner.id
            INNER JOIN product_product pp ON aml.product_id = pp.id
            INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
            INNER JOIN product_category pc ON pt.categ_id = pc.id
        """

    def _where_sales(self):
        return """
            move.move_type IN ('out_invoice', 'out_refund')
            AND move.state = 'posted'
            AND journal.x_treatment IN ('fiscal_real', 'not_fiscal_real', 'fiscal_simulated', 'not_fiscal_simulated')
            AND aml.display_type = 'product'
        """

    def _group_by_sales(self):
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
            move.invoice_date,
            journal.x_treatment,
            move.payment_state,
            pt.manufacturer_id
        """
    
    def _select_pos_aggregated(self):
        return """
            SELECT
                NULL::integer AS move_id,
                pos_order.company_id,
                pos_order.user_id,
                pos_order.crm_team_id AS team_id,
                COALESCE(pos_order.partner_id, 1) AS partner_id,
                COALESCE(pos_order.partner_id, 1) AS commercial_partner_id,
                pol.product_id,
                pc.id AS product_category_id,
                CASE
                    WHEN pc.parent_id = pc.root_categ_id THEN pc.id
                    ELSE pc.parent_id
                END AS parent_categ_id,
                pc.root_categ_id,
                pos_order.date_order AS invoice_date,
                'fiscal_real'::text AS x_treatment,
                'pos'::text AS sale_channel,
                
                SUM(pol.qty) AS quantity,
                SUM(pol.price_subtotal_incl) AS sale_price_total,
                -- Weighted average purchase price
                CASE WHEN SUM(pol.qty) > 0 
                    THEN SUM(pol.qty * COALESCE(CAST(pp.standard_price->>pos_order.company_id::text AS NUMERIC), 0)) / SUM(pol.qty)
                    ELSE 0 END AS purchase_price,
                SUM(pol.qty * COALESCE(CAST(pp.standard_price->>pos_order.company_id::text AS NUMERIC), 0)) AS cost_purchase_total,
                
                AVG(pol.price_unit) AS price_unit,
                AVG(COALESCE(pol.discount, 0)) AS discount,
                SUM(pol.price_subtotal_incl - (pol.qty * COALESCE(CAST(pp.standard_price->>pos_order.company_id::text AS NUMERIC), 0))) AS margin,
                0 AS margin_percent,
                
                -- Collection Management Fields (POS is always fully paid)
                SUM(pol.price_subtotal_incl) AS invoice_amount_total,
                SUM(pol.price_subtotal_incl) AS amount_paid,
                0::numeric AS amount_due,
                SUM(pol.price_subtotal_incl) AS collected_price_total,
                SUM(pol.price_subtotal_incl - (pol.qty * COALESCE(CAST(pp.standard_price->>pos_order.company_id::text AS NUMERIC), 0))) AS collected_margin,
                
                'paid'::text AS payment_state,
                pt.manufacturer_id
        """
    
    def _from_pos(self):
        return """
            pos_order_line pol
            INNER JOIN pos_order ON pol.order_id = pos_order.id
            INNER JOIN product_product pp ON pol.product_id = pp.id
            INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
            INNER JOIN product_category pc ON pt.categ_id = pc.id
        """
    
    def _where_pos(self):
        return """
            pos_order.state IN ('paid', 'done', 'invoiced')
            AND pol.product_id IS NOT NULL
            AND pol.qty > 0
        """
    
    def _group_by_pos(self):
        return """
            pos_order.user_id,
            pos_order.company_id,
            pos_order.crm_team_id,
            pos_order.partner_id,
            pol.product_id,
            pc.id,
            pc.parent_id,
            pc.root_categ_id,
            pos_order.date_order,
            pt.manufacturer_id
        """