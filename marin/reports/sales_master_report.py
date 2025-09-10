from odoo import api, fields, models


class SalesMasterReport(models.Model):
    _name = "sales.master.report"
    _description = "Sales Master Report"
    _auto = False
    _order = "team_id, partner_id, invoice_date DESC"
    _rec_name = "display_name"

    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    invoice_date = fields.Date(string="Invoice Date", readonly=True)
    team_id = fields.Many2one("crm.team", string="Sales Team", readonly=True)
    move_id = fields.Many2one("account.move", string="Invoice Reference", readonly=True)

    quantity = fields.Float(string="Sales Quantity", readonly=True)
    quantity_variation_oyb = fields.Float(string="Quantity Variation % OYB", readonly=True)
    cost_variation_oyb = fields.Float(string="Cost Variation % OYB", readonly=True)
    price_variation_oyb = fields.Float(string="Price Variation % OYB", readonly=True)
    sales_value_variation_oyb = fields.Float(string="Sales Value Variation % OYB", readonly=True)
    margin_variation_oyb = fields.Float(string="Margin Variation % OYB", readonly=True)
    absolute_price_avg = fields.Float(string="Weighted Average List Price", readonly=True)
    sale_price_total = fields.Float(string="Total Sales Value", readonly=True)
    purchase_price = fields.Float(string="Average Purchase Cost", readonly=True)
    cost_purchase_total = fields.Float(string="Total Purchase Cost", readonly=True)
    margin = fields.Float(string="Total Margin Value", readonly=True)

    display_name = fields.Char(string="Description", compute="_compute_display_name", store=False)

    @api.depends("product_id", "partner_id", "invoice_date")
    def _compute_display_name(self):
        for record in self:
            components = []
            if record.product_id:
                components.append(record.product_id.name)
            if record.partner_id:
                components.append(f"- {record.partner_id.name}")
            if record.invoice_date:
                components.append(f"({record.invoice_date})")
            record.display_name = " ".join(components) if components else f"Record #{record.id}"

    @property
    def _table_query(self):
        return self._get_query()

    @api.model
    def _get_query(self):
        return """
            WITH current_data AS (
                SELECT
                    ROW_NUMBER() OVER ()::integer AS id,
                    move.company_id::integer,
                    move.invoice_user_id::integer AS user_id,
                    move.partner_id::integer,
                    aml.product_id::integer,
                    move.invoice_date::date,
                    move.team_id::integer,
                    move.id::integer AS move_id,
                    
                    SUM(aml.quantity)::numeric AS quantity,
                    SUM(aml.price_total)::numeric AS sale_price_total,
                    
                    SUM(aml.quantity * COALESCE(aml.purchase_price, 0)) 
                        / NULLIF(SUM(aml.quantity), 0) AS purchase_price,
                    
                    SUM(aml.quantity * COALESCE(template.list_price, aml.price_unit)) 
                        / NULLIF(SUM(aml.quantity), 0) AS absolute_price_avg,
                    
                    SUM(aml.quantity * COALESCE(aml.purchase_price, 0))::numeric AS cost_purchase_total,
                    
                    (SUM(aml.price_total) - 
                     SUM(aml.quantity * COALESCE(aml.purchase_price, 0)))::numeric AS margin
                FROM account_move_line aml
                    INNER JOIN account_move move ON aml.move_id = move.id
                    INNER JOIN account_journal journal ON move.journal_id = journal.id
                    INNER JOIN crm_team team ON move.team_id = team.id
                    LEFT JOIN product_product product ON aml.product_id = product.id
                    LEFT JOIN product_template template ON product.product_tmpl_id = template.id
                WHERE
                    move.move_type = 'out_invoice'
                    AND move.state = 'posted'
                    AND journal.x_treatment IN (
                        'fiscal_real', 'not_fiscal_real'
                    )
                    AND aml.product_id IS NOT NULL
                    AND aml.quantity > 0
                    AND aml.display_type = 'product'
                    AND move.team_id IS NOT NULL
                    AND team.active = true
                GROUP BY
                    move.company_id,
                    move.invoice_user_id,
                    move.partner_id,
                    aml.product_id,
                    move.invoice_date,
                    move.team_id,
                    move.id
            ),
            
            previous_year_data AS (
                SELECT
                    move.company_id,
                    move.partner_id,
                    aml.product_id,
                    EXTRACT(YEAR FROM move.invoice_date) AS year_data,
                    EXTRACT(MONTH FROM move.invoice_date) AS month_data,
                    
                    SUM(aml.quantity) AS prev_quantity,
                    
                    SUM(aml.quantity * COALESCE(aml.purchase_price, 0)) 
                        / NULLIF(SUM(aml.quantity), 0) AS prev_purchase_price,
                    
                    SUM(aml.price_total) 
                        / NULLIF(SUM(aml.quantity), 0) AS prev_unit_price,
                    
                    SUM(aml.price_total) AS prev_sale_price_total,
                    
                    (SUM(aml.price_total) - 
                     SUM(aml.quantity * COALESCE(aml.purchase_price, 0))) AS prev_margin
                FROM account_move_line aml
                    INNER JOIN account_move move ON aml.move_id = move.id
                    INNER JOIN account_journal journal ON move.journal_id = journal.id
                    INNER JOIN crm_team team ON move.team_id = team.id
                    LEFT JOIN product_product product ON aml.product_id = product.id
                    LEFT JOIN product_template template ON product.product_tmpl_id = template.id
                WHERE
                    move.move_type = 'out_invoice'
                    AND move.state = 'posted'
                    AND journal.x_treatment IN (
                        'fiscal_real', 'not_fiscal_real'
                    )
                    AND aml.product_id IS NOT NULL
                    AND aml.quantity > 0
                    AND aml.display_type = 'product'
                    AND move.team_id IS NOT NULL
                    AND team.active = true
                GROUP BY
                    move.company_id,
                    move.partner_id,
                    aml.product_id,
                    EXTRACT(YEAR FROM move.invoice_date),
                    EXTRACT(MONTH FROM move.invoice_date)
            )
            
            SELECT
                current_data.id,
                current_data.company_id,
                current_data.user_id,
                current_data.partner_id,
                current_data.product_id,
                current_data.invoice_date,
                current_data.team_id,
                current_data.move_id,
                
                current_data.quantity,
                CASE 
                    WHEN previous_year_data.prev_quantity > 0 THEN
                        ROUND((
                            (current_data.quantity - previous_year_data.prev_quantity) 
                            / previous_year_data.prev_quantity
                        ) * 100.0, 2)
                    ELSE 0
                END AS quantity_variation_oyb,
                
                CASE 
                    WHEN previous_year_data.prev_purchase_price > 0 THEN
                        ROUND((
                            (current_data.purchase_price - previous_year_data.prev_purchase_price) 
                            / previous_year_data.prev_purchase_price
                        ) * 100.0, 2)
                    ELSE 0
                END AS cost_variation_oyb,
                
                CASE 
                    WHEN previous_year_data.prev_unit_price > 0 THEN
                        ROUND((
                            (current_data.absolute_price_avg - previous_year_data.prev_unit_price) 
                            / previous_year_data.prev_unit_price
                        ) * 100.0, 2)
                    ELSE 0
                END AS price_variation_oyb,
                
                CASE 
                    WHEN previous_year_data.prev_sale_price_total > 0 THEN
                        ROUND((
                            (current_data.sale_price_total - previous_year_data.prev_sale_price_total) 
                            / previous_year_data.prev_sale_price_total
                        ) * 100.0, 2)
                    ELSE 0
                END AS sales_value_variation_oyb,
                
                CASE 
                    WHEN previous_year_data.prev_margin > 0 THEN
                        ROUND((
                            (current_data.margin - previous_year_data.prev_margin) 
                            / previous_year_data.prev_margin
                        ) * 100.0, 2)
                    ELSE 0
                END AS margin_variation_oyb,
                current_data.absolute_price_avg,
                current_data.sale_price_total,
                current_data.purchase_price,
                current_data.cost_purchase_total,
                current_data.margin
                
            FROM current_data
                LEFT JOIN previous_year_data ON (
                    current_data.company_id = previous_year_data.company_id
                    AND current_data.partner_id = previous_year_data.partner_id
                    AND current_data.product_id = previous_year_data.product_id
                    AND EXTRACT(YEAR FROM current_data.invoice_date) - 1 = 
                        previous_year_data.year_data
                    AND EXTRACT(MONTH FROM current_data.invoice_date) = 
                        previous_year_data.month_data
                )
        """
