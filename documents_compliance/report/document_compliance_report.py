from odoo import api, fields, models, tools


class DocumentComplianceReport(models.Model):
    """General document compliance reporting view."""

    _name = "document.compliance.report"
    _description = "Document Compliance Report"
    _auto = False
    _rec_name = "name"
    _order = "compliance_percentage"

    # Document information
    name = fields.Char("Entity", readonly=True)
    entity_type = fields.Char("Entity Type", readonly=True)
    entity_id = fields.Integer("Entity ID", readonly=True)

    # Document type information
    document_type_id = fields.Many2one("document.type", "Document Type", readonly=True)
    document_type_code = fields.Char("Type Code", readonly=True)
    is_mandatory = fields.Boolean("Mandatory", readonly=True)

    # Compliance metrics
    total_required = fields.Integer("Required Documents", readonly=True)
    total_present = fields.Integer("Present Documents", readonly=True)
    total_valid = fields.Integer("Valid Documents", readonly=True)
    total_expired = fields.Integer("Expired Documents", readonly=True)
    total_expiring = fields.Integer("Expiring Soon", readonly=True)
    total_missing = fields.Integer("Missing Documents", readonly=True)

    # Compliance status
    compliance_percentage = fields.Float(
        "Compliance %", readonly=True, group_operator="avg"
    )
    is_compliant = fields.Boolean("Fully Compliant", readonly=True)
    compliance_status = fields.Selection(
        [
            ("compliant", "Compliant"),
            ("partial", "Partial Compliance"),
            ("non_compliant", "Non-Compliant"),
        ],
        "Status",
        readonly=True,
    )

    # Dates
    earliest_expiry = fields.Date("Next Expiry", readonly=True)
    last_verification = fields.Date("Last Verification", readonly=True)

    # Company
    company_id = fields.Many2one("res.company", "Company", readonly=True)

    def init(self):
        """Create or replace the SQL view for compliance reporting."""
        tools.drop_view_if_exists(self.env.cr, self._table)

        # This creates a generic view that can be extended by other modules
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                WITH document_stats AS (
                    SELECT
                        dt.id as document_type_id,
                        dt.code as document_type_code,
                        dt.name as document_type_name,
                        dt.is_mandatory,
                        dt.company_id,
                        dd.id as document_id,
                        dd.name as document_name,
                        dd.compliance_status,
                        dd.expired,
                        dd.date_expiration,
                        dd.verification_date,
                        CASE
                            WHEN dd.compliance_status = 'valid' THEN 1
                            ELSE 0
                        END as is_valid,
                        CASE
                            WHEN dd.compliance_status = 'expired' THEN 1
                            ELSE 0
                        END as is_expired,
                        CASE
                            WHEN dd.compliance_status = 'expiring_soon' THEN 1
                            ELSE 0
                        END as is_expiring
                    FROM document_type dt
                    LEFT JOIN documents_document dd ON dd.document_type_id = dt.id
                    WHERE dt.active = true
                )
                SELECT
                    row_number() OVER () AS id,
                    dt.name as name,
                    'Document Type' as entity_type,
                    dt.id as entity_id,
                    dt.id as document_type_id,
                    dt.code as document_type_code,
                    dt.is_mandatory,
                    COUNT(DISTINCT CASE WHEN dt.is_mandatory THEN dt.id END) as total_required,
                    COUNT(ds.document_id) as total_present,
                    SUM(ds.is_valid) as total_valid,
                    SUM(ds.is_expired) as total_expired,
                    SUM(ds.is_expiring) as total_expiring,
                    COUNT(DISTINCT CASE WHEN dt.is_mandatory AND ds.document_id IS NULL THEN dt.id END) as total_missing,
                    CASE
                        WHEN COUNT(DISTINCT CASE WHEN dt.is_mandatory THEN dt.id END) = 0 THEN 100
                        ELSE (SUM(ds.is_valid)::float / NULLIF(COUNT(ds.document_id), 0)::float) * 100
                    END as compliance_percentage,
                    CASE
                        WHEN COUNT(DISTINCT CASE WHEN dt.is_mandatory THEN dt.id END) = SUM(ds.is_valid) THEN true
                        ELSE false
                    END as is_compliant,
                    CASE
                        WHEN COUNT(DISTINCT CASE WHEN dt.is_mandatory THEN dt.id END) = SUM(ds.is_valid) THEN 'compliant'
                        WHEN SUM(ds.is_valid) > 0 THEN 'partial'
                        ELSE 'non_compliant'
                    END as compliance_status,
                    MIN(ds.date_expiration) as earliest_expiry,
                    MAX(ds.verification_date) as last_verification,
                    dt.company_id
                FROM document_type dt
                LEFT JOIN document_stats ds ON ds.document_type_id = dt.id
                GROUP BY dt.id, dt.name, dt.code, dt.is_mandatory, dt.company_id
            )
        """
            % self._table
        )

    @api.model
    def get_compliance_summary(self):
        """Get overall compliance summary statistics."""
        self.env.cr.execute(
            """
            SELECT
                COUNT(*) as total_entities,
                SUM(CASE WHEN is_compliant THEN 1 ELSE 0 END) as compliant_entities,
                AVG(compliance_percentage) as avg_compliance,
                SUM(total_expired) as total_expired,
                SUM(total_expiring) as total_expiring,
                SUM(total_missing) as total_missing
            FROM document_compliance_report
            WHERE company_id = %s
        """,
            (self.env.company.id,),
        )

        return self.env.cr.dictfetchone()

    def action_view_documents(self):
        """View documents for this compliance entry."""
        self.ensure_one()

        domain = [("document_type_id", "=", self.document_type_id.id)]

        return {
            "name": f"Documents: {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "documents.document",
            "view_mode": "kanban,list",
            "domain": domain,
            "context": {
                "default_document_type_id": self.document_type_id.id,
            },
        }
