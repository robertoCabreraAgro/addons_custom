from odoo import api, fields, models, tools


class AssetComplianceReport(models.Model):
    """Asset-specific compliance reporting view."""

    _name = "asset.compliance.report"
    _description = "Asset Compliance Report"
    _auto = False
    _rec_name = "asset_name"
    _order = "compliance_percentage"

    # Asset information
    asset_id = fields.Many2one("product.template", "Asset", readonly=True)
    asset_name = fields.Char("Asset Name", readonly=True)
    asset_type = fields.Selection(
        [
            ("vehicle", "Vehicle"),
            ("machinery", "Machinery"),
            ("property", "Property"),
            ("product", "IT Asset"),
        ],
        "Asset Type",
        readonly=True,
    )

    # Serial/Lot information
    lot_id = fields.Many2one("stock.lot", "Serial/Lot", readonly=True)
    lot_name = fields.Char("Serial Number", readonly=True)

    # Asset details
    asset_manager_id = fields.Many2one("hr.employee", "Asset Manager", readonly=True)
    location_id = fields.Many2one("stock.location", "Current Location", readonly=True)

    # Document statistics
    total_documents = fields.Integer("Total Documents", readonly=True)
    total_required = fields.Integer("Required Documents", readonly=True)
    total_valid = fields.Integer("Valid Documents", readonly=True)
    total_expired = fields.Integer("Expired Documents", readonly=True)
    total_expiring = fields.Integer("Expiring Soon (30 days)", readonly=True)
    total_missing = fields.Integer("Missing Documents", readonly=True)

    # Compliance metrics
    compliance_percentage = fields.Float(
        "Compliance %", readonly=True, group_operator="avg"
    )
    is_compliant = fields.Boolean("Fully Compliant", readonly=True)
    compliance_status = fields.Selection(
        [
            ("compliant", "Compliant"),
            ("partial", "Partial Compliance"),
            ("non_compliant", "Non-Compliant"),
            ("no_requirements", "No Requirements"),
        ],
        "Compliance Status",
        readonly=True,
    )

    # Critical dates
    next_expiry_date = fields.Date("Next Expiry", readonly=True)
    last_verification_date = fields.Date("Last Verification", readonly=True)

    # Company
    company_id = fields.Many2one("res.company", "Company", readonly=True)

    def init(self):
        """Create or replace the SQL view for asset compliance reporting."""
        tools.drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                WITH asset_documents AS (
                    -- Get all documents linked to assets
                    SELECT
                        pt.id as asset_id,
                        pt.name as asset_name,
                        pt.asset_type,
                        sl.asset_manager_id,
                        pt.company_id,
                        sl.id as lot_id,
                        sl.name as lot_name,
                        sq.location_id,
                        dd.id as document_id,
                        dd.document_type_id,
                        dd.compliance_status,
                        dd.is_mandatory,
                        dd.date_expiration,
                        dd.verification_date,
                        dd.expired
                    FROM product_template pt
                    LEFT JOIN product_product pp ON pp.product_tmpl_id = pt.id
                    LEFT JOIN stock_lot sl ON sl.product_id = pp.id
                    LEFT JOIN stock_quant sq ON sq.lot_id = sl.id AND sq.quantity > 0
                    LEFT JOIN documents_document dd ON dd.asset_id = pt.id
                        OR (dd.res_model = 'stock.lot' AND dd.res_id = sl.id)
                    WHERE pt.asset_type IS NOT NULL
                ),
                asset_requirements AS (
                    -- Get required document types per asset type
                    SELECT
                        pt.id as asset_id,
                        dt.id as document_type_id,
                        dt.is_mandatory
                    FROM product_template pt
                    CROSS JOIN document_type dt
                    WHERE pt.asset_type IS NOT NULL
                        AND dt.active = true
                        AND dt.is_mandatory = true
                        AND (
                            dt.id IN (
                                SELECT unnest(string_to_array('', ',')::int[])
                                WHERE false -- Placeholder for asset-specific rules
                            )
                            OR true -- For now, apply to all assets
                        )
                )
                SELECT
                    row_number() OVER () AS id,
                    pt.id as asset_id,
                    pt.name as asset_name,
                    pt.asset_type,
                    MIN(sl.asset_manager_id) as asset_manager_id,
                    pt.company_id,
                    MIN(sl.id) as lot_id,
                    MIN(sl.name) as lot_name,
                    MIN(sq.location_id) as location_id,

                    -- Document counts
                    COUNT(DISTINCT ad.document_id) as total_documents,
                    COUNT(DISTINCT ar.document_type_id) as total_required,
                    COUNT(DISTINCT CASE
                        WHEN ad.compliance_status = 'valid' AND ad.is_mandatory
                        THEN ad.document_type_id
                    END) as total_valid,
                    COUNT(DISTINCT CASE
                        WHEN ad.expired = true OR ad.compliance_status = 'expired'
                        THEN ad.document_id
                    END) as total_expired,
                    COUNT(DISTINCT CASE
                        WHEN ad.compliance_status = 'expiring_soon'
                        THEN ad.document_id
                    END) as total_expiring,
                    COUNT(DISTINCT ar.document_type_id) - COUNT(DISTINCT CASE
                        WHEN ad.is_mandatory
                        THEN ad.document_type_id
                    END) as total_missing,

                    -- Compliance calculation
                    CASE
                        WHEN COUNT(DISTINCT ar.document_type_id) = 0 THEN 100
                        WHEN COUNT(DISTINCT ar.document_type_id) > 0 THEN
                            (COUNT(DISTINCT CASE
                                WHEN ad.compliance_status = 'valid' AND ad.is_mandatory
                                THEN ad.document_type_id
                            END)::float / COUNT(DISTINCT ar.document_type_id)::float) * 100
                        ELSE 0
                    END as compliance_percentage,

                    -- Compliance status
                    CASE
                        WHEN COUNT(DISTINCT ar.document_type_id) = 0 THEN true
                        WHEN COUNT(DISTINCT ar.document_type_id) = COUNT(DISTINCT CASE
                            WHEN ad.compliance_status = 'valid' AND ad.is_mandatory
                            THEN ad.document_type_id
                        END) THEN true
                        ELSE false
                    END as is_compliant,

                    CASE
                        WHEN COUNT(DISTINCT ar.document_type_id) = 0 THEN 'no_requirements'
                        WHEN COUNT(DISTINCT ar.document_type_id) = COUNT(DISTINCT CASE
                            WHEN ad.compliance_status = 'valid' AND ad.is_mandatory
                            THEN ad.document_type_id
                        END) THEN 'compliant'
                        WHEN COUNT(DISTINCT CASE
                            WHEN ad.compliance_status = 'valid' AND ad.is_mandatory
                            THEN ad.document_type_id
                        END) > 0 THEN 'partial'
                        ELSE 'non_compliant'
                    END as compliance_status,

                    -- Dates
                    MIN(CASE
                        WHEN ad.date_expiration > CURRENT_DATE
                        THEN ad.date_expiration
                    END) as next_expiry_date,
                    MAX(ad.verification_date) as last_verification_date

                FROM product_template pt
                LEFT JOIN product_product pp ON pp.product_tmpl_id = pt.id
                LEFT JOIN stock_lot sl ON sl.product_id = pp.id
                LEFT JOIN stock_quant sq ON sq.lot_id = sl.id AND sq.quantity > 0
                LEFT JOIN asset_documents ad ON ad.asset_id = pt.id
                LEFT JOIN asset_requirements ar ON ar.asset_id = pt.id
                WHERE pt.asset_type IS NOT NULL
                GROUP BY pt.id, pt.name, pt.asset_type, pt.company_id
            )
        """
            % self._table
        )

    @api.model
    def get_asset_compliance_by_type(self):
        """Get compliance summary grouped by asset type."""
        self.env.cr.execute(
            """
            SELECT
                asset_type,
                COUNT(*) as total_assets,
                SUM(CASE WHEN is_compliant THEN 1 ELSE 0 END) as compliant_assets,
                AVG(compliance_percentage) as avg_compliance,
                SUM(total_expired) as total_expired,
                SUM(total_expiring) as total_expiring
            FROM asset_compliance_report
            WHERE company_id = %s
            GROUP BY asset_type
            ORDER BY asset_type
        """,
            (self.env.company.id,),
        )

        return self.env.cr.dictfetchall()

    def action_view_asset_documents(self):
        """View all documents for this asset."""
        self.ensure_one()

        return {
            "name": f"Documents: {self.asset_name}",
            "type": "ir.actions.act_window",
            "res_model": "documents.document",
            "view_mode": "kanban,list",
            "domain": [
                "|",
                ("asset_id", "=", self.asset_id.id),
                "&",
                ("res_model", "=", "stock.lot"),
                ("res_id", "=", self.lot_id.id) if self.lot_id else ("id", "=", False),
            ],
            "context": {
                "default_asset_id": self.asset_id.id,
                "default_res_model": "stock.lot" if self.lot_id else False,
                "default_res_id": self.lot_id.id if self.lot_id else False,
            },
        }

    def action_view_missing_documents(self):
        """Show what documents are missing for this asset."""
        self.ensure_one()

        # This would show a wizard or view with required document types
        # that don't have valid documents attached
        return {
            "type": "ir.actions.act_window",
            "name": f"Missing Documents for {self.asset_name}",
            "res_model": "document.type",
            "view_mode": "list",
            "domain": [
                ("is_mandatory", "=", True),
                # Additional domain to filter by what's missing
            ],
        }
