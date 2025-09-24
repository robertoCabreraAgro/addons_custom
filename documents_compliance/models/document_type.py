from datetime import timedelta
from odoo import api, fields, models


class DocumentType(models.Model):
    """Document type configuration for compliance and categorization."""

    _name = "document.type"
    _description = "Document Type"
    _order = "sequence, name"
    _rec_name = "name"

    # Basic Information
    name = fields.Char(string="Document Type", required=True, translate=True)
    code = fields.Char(string="Code", required=True, index=True)
    sequence = fields.Integer(default=10, help="Used to order document types")
    active = fields.Boolean(default=True)
    description = fields.Text(string="Description", translate=True)

    # Compliance Requirements
    is_mandatory = fields.Boolean(
        string="Mandatory Document",
        help="This document is required for compliance",
    )
    is_renewable = fields.Boolean(
        string="Renewable Document",
        default=True,
        help="This document can be renewed when it expires",
    )
    requires_original = fields.Boolean(
        string="Requires Original",
        help="Physical original document must be kept",
    )

    # Validity Settings
    has_expiration = fields.Boolean(
        string="Has Expiration",
        default=True,
        help="This document type has an expiration date",
    )
    default_validity_days = fields.Integer(
        string="Default Validity (days)",
        help="Default validity period in days for new documents of this type",
    )
    auto_renew_days_before = fields.Integer(
        string="Auto-Renewal Reminder (days)",
        default=30,
        help="Days before expiration to trigger renewal reminder",
    )

    # Notification Settings
    notification_days = fields.Char(
        string="Notification Days",
        default="30,7,1",
        help="Comma-separated days before expiration to send notifications (e.g., 30,7,1)",
    )
    notification_partner_ids = fields.Many2many(
        "res.partner",
        "document_type_partner_rel",
        "type_id",
        "partner_id",
        string="Additional Recipients",
        help="Partners to notify in addition to document owner",
    )

    # Document Tags (Integration with documents module)
    tag_ids = fields.Many2many(
        "documents.tag",
        "document_type_tag_rel",
        "type_id",
        "tag_id",
        string="Default Tags",
        help="Tags automatically applied to documents of this type",
    )

    # Folder Organization
    folder_id = fields.Many2one(
        "documents.document",
        string="Default Folder",
        domain="[('type', '=', 'folder')]",
        help="Default folder for documents of this type",
    )

    # Template and Instructions
    template_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Document Template",
        help="Template file for this document type",
    )
    instructions = fields.Html(
        string="Instructions",
        translate=True,
        help="Instructions for obtaining or renewing this document",
    )

    # Statistics
    document_count = fields.Integer(
        string="Documents",
        compute="_compute_document_count",
    )
    expired_document_count = fields.Integer(
        string="Expired Documents",
        compute="_compute_document_count",
    )
    expiring_soon_count = fields.Integer(
        string="Expiring Soon",
        compute="_compute_document_count",
    )

    # Company
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    @api.depends("code")
    def _compute_document_count(self):
        """Compute document statistics for each type."""
        DocumentDocument = self.env["documents.document"]
        today = fields.Date.today()

        for doc_type in self:
            documents = DocumentDocument.search(
                [("document_type_id", "=", doc_type.id)]
            )
            doc_type.document_count = len(documents)

            # Count expired documents
            doc_type.expired_document_count = len(
                documents.filtered(
                    lambda d: d.expired
                    or (d.date_expiration and d.date_expiration < today)
                )
            )

            # Count expiring soon (within 30 days)
            expiring_date = today + timedelta(days=30)
            doc_type.expiring_soon_count = len(
                documents.filtered(
                    lambda d: d.date_expiration
                    and today < d.date_expiration <= expiring_date
                )
            )

    @api.model
    def get_notification_days_list(self):
        """Parse notification days into a list of integers."""
        if not self.notification_days:
            return []
        try:
            return [
                int(d.strip()) for d in self.notification_days.split(",") if d.strip()
            ]
        except ValueError:
            return [30, 7, 1]  # Default fallback

    def action_view_documents(self):
        """View all documents of this type."""
        self.ensure_one()
        return {
            "name": f"{self.name} Documents",
            "type": "ir.actions.act_window",
            "res_model": "documents.document",
            "view_mode": "tree,form",
            "domain": [("document_type_id", "=", self.id)],
            "context": {
                "default_document_type_id": self.id,
                "default_folder_id": self.folder_id.id,
                "default_tag_ids": [(6, 0, self.tag_ids.ids)],
            },
        }
