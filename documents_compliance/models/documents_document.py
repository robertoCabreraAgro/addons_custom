from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import UserError


class Documents(models.Model):
    _inherit = "documents.document"

    issuer_id = fields.Many2one(
        comodel_name="res.partner",
        string="Issued by",
        help="The authority that issued this licence",
    )
    issued_date = fields.Date(
        help="The date on which this document was issued",
    )
    date_expiration = fields.Date(
        help="The date on which this document will be expired. Leave it blank for non-expiration",
    )
    days_left = fields.Integer(
        string="Days to expire",
        compute="_compute_days_left",
        help="The number of days to the expired date",
    )
    expired = fields.Boolean(default=False)

    # Document Type and Compliance
    legal_number = fields.Char(
        string="Legal number",
    )
    document_type_id = fields.Many2one(
        comodel_name="document.type",
        string="Document Type",
        help="Type of document for compliance tracking",
    )

    is_mandatory = fields.Boolean(
        related="document_type_id.is_mandatory",
        store=True,
        string="Mandatory Document",
    )

    is_renewable = fields.Boolean(
        related="document_type_id.is_renewable",
        store=True,
        string="Renewable",
    )

    # Enhanced Notification Tracking
    notification_sent_30 = fields.Boolean(
        string="30-day notification sent",
        default=False,
        help="Notification sent 30 days before expiration",
    )
    notification_sent_7 = fields.Boolean(
        string="7-day notification sent",
        default=False,
        help="Notification sent 7 days before expiration",
    )
    notification_sent_1 = fields.Boolean(
        string="1-day notification sent",
        default=False,
        help="Notification sent 1 day before expiration",
    )
    notification_sent_expired = fields.Boolean(
        string="Expiration notification sent",
        default=False,
        help="Notification sent when document expired",
    )

    # Renewal Tracking
    renewal_document_id = fields.Many2one(
        comodel_name="documents.document",
        string="Renewal Of",
        help="Previous version this document renews",
    )
    renewed_by_document_id = fields.Many2one(
        comodel_name="documents.document",
        string="Renewed By",
        help="Document that renewed this one",
    )
    renewal_count = fields.Integer(
        string="Times Renewed",
        compute="_compute_renewal_count",
        store=True,
    )

    # Compliance Status
    compliance_status = fields.Selection(
        selection=[
            ("valid", "Valid"),
            ("expiring_soon", "Expiring Soon"),
            ("expired", "Expired"),
            ("missing", "Missing"),
            ("na", "Not Applicable"),
        ],
        string="Compliance Status",
        compute="_compute_compliance_status",
        store=True,
    )

    # Verification
    verification_date = fields.Date(
        string="Verification Date",
        help="Date when document was last verified",
    )
    verified_by_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Verified By",
        help="User who verified this document",
    )
    verification_notes = fields.Text(string="Verification Notes")

    @api.constrains("legal_number")
    def _check_duplicated_legal_number(self):
        for doc in self:
            overlap = self.env["documents.document"].search_count(
                [("id", "!=", doc.id), ("legal_number", "=", doc.legal_number)]
            )
            if overlap >= 1:
                raise UserError(
                    _(
                        'A document with legal number "%s - %s" already exists.',
                        doc.display_name,
                        doc.legal_number,
                    ),
                )

    @api.depends("date_expiration")
    def _compute_days_left(self):
        for record in self:
            if not record.date_expiration:
                record.days_left = 365
            else:
                today = fields.Date.today()
                record.days_left = (record.date_expiration - today).days

    @api.depends("renewal_document_id")
    def _compute_renewal_count(self):
        """Count how many times this document has been renewed."""
        for doc in self:
            count = 0
            current = doc
            while current.renewal_document_id:
                count += 1
                current = current.renewal_document_id
                # Prevent infinite loops
                if count > 100:
                    break
            doc.renewal_count = count

    @api.depends("date_expiration", "expired")
    def _compute_compliance_status(self):
        """Compute compliance status based on expiration."""
        today = fields.Date.today()
        for doc in self:
            if not doc.document_type_id or not doc.document_type_id.has_expiration:
                doc.compliance_status = "na"
            elif doc.expired:
                doc.compliance_status = "expired"
            elif not doc.date_expiration:
                doc.compliance_status = "missing"
            elif doc.date_expiration < today:
                doc.compliance_status = "expired"
            elif doc.date_expiration <= today + timedelta(days=30):
                doc.compliance_status = "expiring_soon"
            else:
                doc.compliance_status = "valid"

    @api.onchange("document_type_id")
    def _onchange_document_type_id(self):
        """Apply document type defaults."""
        if self.document_type_id:
            # Set folder
            if self.document_type_id.folder_id:
                self.folder_id = self.document_type_id.folder_id

            # Set tags
            if self.document_type_id.tag_ids:
                self.tag_ids = [(6, 0, self.document_type_id.tag_ids.ids)]

            # Set default expiration if applicable
            if (
                self.document_type_id.has_expiration
                and self.document_type_id.default_validity_days
            ):
                if not self.date_expiration or not self.issued_date:
                    self.issued_date = fields.Date.today()
                    self.date_expiration = fields.Date.today() + timedelta(
                        days=self.document_type_id.default_validity_days
                    )

    def action_set_expired(self):
        self.write({"expired": True})

    def action_renew(self):
        self.write({"expired": False})

    def cron_find_and_set_expired(self):
        to_set_expired = self.search(
            [
                ("date_expiration", "!=", False),
                ("date_expiration", "<=", fields.Date.today()),
            ]
        )
        if to_set_expired:
            to_set_expired.with_context(cron_mode=True).action_set_expired()
        return True

    def action_renew_document(self):
        """Create a renewal document."""
        self.ensure_one()

        if not self.is_renewable:
            raise UserError("This document type is not renewable.")

        # Create new document as renewal
        new_doc = self.copy(
            {
                "name": f"{self.name} (Renewal)",
                "renewal_document_id": self.id,
                "issued_date": fields.Date.today(),
                "date_expiration": False,
                "expired": False,
                "notification_sent_30": False,
                "notification_sent_7": False,
                "notification_sent_1": False,
                "notification_sent_expired": False,
            }
        )

        # Set expiration based on document type
        if self.document_type_id and self.document_type_id.default_validity_days:
            new_doc.date_expiration = fields.Date.today() + timedelta(
                days=self.document_type_id.default_validity_days
            )

        # Mark this document as renewed
        self.renewed_by_document_id = new_doc

        # Return action to view new document
        return {
            "type": "ir.actions.act_window",
            "res_model": "documents.document",
            "res_id": new_doc.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_verify_document(self):
        """Mark document as verified."""
        self.ensure_one()
        self.write(
            {
                "verification_date": fields.Date.today(),
                "verified_by_user_id": self.env.user.id,
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Document Verified",
                "message": f"Document {self.name} has been verified.",
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def cron_document_notifications(self):
        """Enhanced daily cron job for document expiration notifications."""
        today = fields.Date.today()

        # Process notifications for different time periods
        notification_periods = [
            (30, "notification_sent_30"),
            (7, "notification_sent_7"),
            (1, "notification_sent_1"),
        ]

        for days, field_name in notification_periods:
            target_date = today + timedelta(days=days)
            domain = [
                ("date_expiration", "=", target_date),
                (field_name, "=", False),
                ("expired", "=", False),
                ("document_type_id", "!=", False),
            ]

            documents = self.search(domain)
            for doc in documents:
                doc._send_expiration_notification(days)
                doc.write({field_name: True})

        # Process expired documents
        expired_docs = self.search(
            [
                ("date_expiration", "=", today),
                ("notification_sent_expired", "=", False),
                ("expired", "=", False),
            ]
        )

        for doc in expired_docs:
            doc._send_expiration_notification(0)
            doc.write(
                {
                    "notification_sent_expired": True,
                    "expired": True,
                }
            )

    def _send_expiration_notification(self, days_left):
        """Send expiration notification to relevant parties."""
        self.ensure_one()

        # Determine recipients
        partners = self.env["res.partner"]

        # Add document type specific recipients
        if self.document_type_id.notification_partner_ids:
            partners |= self.document_type_id.notification_partner_ids

        # Add document owner
        if self.owner_id:
            partners |= self.owner_id.partner_id

        if not partners:
            # Default to current user
            partners = self.env.user.partner_id

        # Create activity for each recipient
        for partner in partners:
            if partner.user_ids:
                user = partner.user_ids[0]

                if days_left > 0:
                    summary = f"Document expiring in {days_left} days"
                else:
                    summary = "Document expired"

                note = self._get_expiration_note(days_left)

                self.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=self.date_expiration or fields.Date.today(),
                    user_id=user.id,
                    summary=summary,
                    note=note,
                )

    def _get_expiration_note(self, days_left):
        """Generate expiration notification message."""
        self.ensure_one()

        if days_left > 0:
            message = f"""
            <p>The following document will expire in <strong>{days_left} days</strong>:</p>
            <ul>
                <li><strong>Document:</strong> {self.name}</li>
                <li><strong>Type:</strong> {self.document_type_id.name if self.document_type_id else 'Not specified'}</li>
                <li><strong>Expiration Date:</strong> {self.date_expiration}</li>
            </ul>
            """
        else:
            message = f"""
            <p>The following document has <strong>expired</strong>:</p>
            <ul>
                <li><strong>Document:</strong> {self.name}</li>
                <li><strong>Type:</strong> {self.document_type_id.name if self.document_type_id else 'Not specified'}</li>
                <li><strong>Expiration Date:</strong> {self.date_expiration}</li>
            </ul>
            """

        if (
            self.is_renewable
            and self.document_type_id
            and self.document_type_id.instructions
        ):
            message += f"""
            <p><strong>Renewal Instructions:</strong></p>
            {self.document_type_id.instructions}
            """

        return message

    @api.model
    def check_compliance_by_tags(self, tag_ids, mandatory_only=True):
        """Check compliance status for documents with specific tags."""
        domain = [("tag_ids", "in", tag_ids)]
        if mandatory_only:
            domain.append(("is_mandatory", "=", True))

        documents = self.search(domain)

        result = {
            "total_documents": len(documents),
            "valid_documents": 0,
            "expired_documents": 0,
            "expiring_soon": 0,
            "missing_documents": 0,
            "compliance_percentage": 0,
            "is_compliant": False,
            "details": [],
        }

        for doc in documents:
            doc_info = {
                "name": doc.name,
                "type": (
                    doc.document_type_id.name if doc.document_type_id else "Unknown"
                ),
                "status": doc.compliance_status,
                "date_expiration": doc.date_expiration,
            }

            if doc.compliance_status == "valid":
                result["valid_documents"] += 1
            elif doc.compliance_status == "expired":
                result["expired_documents"] += 1
            elif doc.compliance_status == "expiring_soon":
                result["expiring_soon"] += 1
            elif doc.compliance_status == "missing":
                result["missing_documents"] += 1

            result["details"].append(doc_info)

        # Calculate compliance percentage
        if result["total_documents"] > 0:
            result["compliance_percentage"] = (
                result["valid_documents"] / result["total_documents"] * 100
            )
            result["is_compliant"] = (
                result["valid_documents"] == result["total_documents"]
            )

        return result
