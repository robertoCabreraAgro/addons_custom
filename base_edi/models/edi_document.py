# -*- coding: utf-8 -*-
"""Enhanced EDI document base for all country implementations."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import logging

_logger = logging.getLogger(__name__)


class EdiDocument(models.AbstractModel):
    """Enhanced EDI document base for all country implementations."""

    _name = "base.edi.document"
    _inherit = "account.edi.document"
    _description = "Base EDI Document"

    # Additional fields for enhanced tracking
    provider_id = fields.Many2one(
        "edi.provider",
        string="EDI Provider",
        help="The service provider used to process this document",
    )

    certificate_id = fields.Many2one(
        "certificate.certificate",
        string="Certificate Used",
        help="Digital certificate used to sign this document",
    )

    signature = fields.Binary(
        string="Digital Signature", help="The digital signature of the document"
    )

    signature_algorithm = fields.Char(
        string="Signature Algorithm",
        help="Algorithm used for digital signature (e.g., RSA-SHA256)",
    )

    signature_timestamp = fields.Datetime(
        string="Signature Timestamp", help="When the document was digitally signed"
    )

    # Enhanced state tracking
    processing_stage = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("signed", "Signed"),
            ("sent", "Sent to Provider"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        string="Processing Stage",
        default="draft",
        tracking=True,
    )

    validation_errors = fields.Text(
        string="Validation Errors",
        help="Detailed validation errors found in the document",
    )

    provider_response = fields.Text(
        string="Provider Response", help="Raw response from the EDI provider"
    )

    provider_tracking_id = fields.Char(
        string="Provider Tracking ID", help="Unique identifier assigned by the provider"
    )

    retry_count = fields.Integer(
        string="Retry Count",
        default=0,
        help="Number of times processing has been retried",
    )

    last_retry_date = fields.Datetime(string="Last Retry Date")

    # Metadata fields
    document_uuid = fields.Char(
        string="Document UUID",
        index=True,
        help="Universally unique identifier for the document",
    )

    document_version = fields.Char(
        string="Document Version", help="Version of the EDI format used"
    )

    processing_time = fields.Float(
        string="Processing Time (seconds)", help="Time taken to process the document"
    )

    @api.model
    def _validate_document(self):
        """
        Base validation to be extended by country modules.

        Returns:
            list: List of validation error messages
        """
        self.ensure_one()
        errors = []

        # Common validations
        if not self.move_id:
            errors.append(_("No accounting move linked to this document"))

        if self.move_id and not self.move_id.partner_id:
            errors.append(_("Partner is required for EDI document"))

        if self.move_id and not self.move_id.company_id:
            errors.append(_("Company is required for EDI document"))

        # Check if certificate is valid if required
        if self._requires_signature() and not self._get_signing_certificate():
            errors.append(_("No valid certificate available for signing"))

        return errors

    @api.model
    def _requires_signature(self):
        """
        Check if this document requires digital signature.
        To be overridden by specific implementations.
        """
        return False

    @api.model
    def _get_signing_certificate(self):
        """
        Get the certificate to use for signing this document.
        To be overridden by specific implementations.
        """
        self.ensure_one()
        if not self.move_id.company_id:
            return False

        # Get valid certificates for the company
        certificates = self.env["certificate.certificate"].search(
            [
                ("company_id", "=", self.move_id.company_id.id),
                ("is_valid", "=", True),
            ]
        )

        # Filter by EDI scope if defined
        edi_certificates = certificates.filtered(
            lambda c: not hasattr(c, "edi_scope") or c.edi_scope == "signing"
        )

        return edi_certificates[:1] if edi_certificates else False

    @api.model
    def _sign_document(self, content, certificate):
        """
        Base signing method using certificate module.

        Args:
            content (bytes): Document content to sign
            certificate (certificate.certificate): Certificate to use for signing

        Returns:
            bytes: Digital signature
        """
        if not certificate:
            raise UserError(_("No certificate provided for signing"))

        # This is a placeholder - actual implementation would use cryptography library
        # to create a digital signature using the certificate's private key
        _logger.info("Signing document with certificate %s", certificate.name)

        # Return placeholder signature
        return base64.b64encode(b"SIGNATURE_PLACEHOLDER")

    def action_validate(self):
        """Validate the EDI document."""
        self.ensure_one()
        errors = self._validate_document()

        if errors:
            self.write(
                {
                    "processing_stage": "draft",
                    "validation_errors": "\n".join(errors),
                    "error": "<br/>".join(errors),
                    "blocking_level": "error",
                }
            )
            raise ValidationError("\n".join(errors))
        else:
            self.write(
                {
                    "processing_stage": "validated",
                    "validation_errors": False,
                    "error": False,
                    "blocking_level": False,
                }
            )

        return True

    def action_sign(self):
        """Sign the EDI document."""
        self.ensure_one()

        if self.processing_stage != "validated":
            self.action_validate()

        certificate = self._get_signing_certificate()
        if not certificate:
            raise UserError(_("No valid certificate found for signing"))

        # Get document content
        content = base64.b64decode(self.edi_content or b"")

        # Sign the document
        signature = self._sign_document(content, certificate)

        self.write(
            {
                "processing_stage": "signed",
                "certificate_id": certificate.id,
                "signature": signature,
                "signature_algorithm": "RSA-SHA256",  # This would be dynamic
                "signature_timestamp": fields.Datetime.now(),
            }
        )

        return True

    def action_send_to_provider(self):
        """Send the document to the EDI provider."""
        self.ensure_one()

        if self.processing_stage not in ("signed", "validated"):
            if self._requires_signature():
                self.action_sign()
            else:
                self.action_validate()

        if not self.provider_id:
            # Try to get default provider
            self.provider_id = self._get_default_provider()

        if not self.provider_id:
            raise UserError(_("No EDI provider configured"))

        # Send to provider (to be implemented by provider class)
        result = self.provider_id.send_document(self)

        if result.get("success"):
            self.write(
                {
                    "processing_stage": "accepted",
                    "provider_tracking_id": result.get("tracking_id"),
                    "provider_response": result.get("response"),
                    "state": "sent",
                }
            )
        else:
            self.write(
                {
                    "processing_stage": "rejected",
                    "provider_response": result.get("error"),
                    "error": result.get("error"),
                    "blocking_level": "error",
                    "retry_count": self.retry_count + 1,
                    "last_retry_date": fields.Datetime.now(),
                }
            )

        return True

    def action_retry(self):
        """Retry processing the document."""
        self.ensure_one()

        if self.retry_count >= 3:
            raise UserError(_("Maximum retry attempts (3) reached"))

        # Reset to validated stage and retry
        self.processing_stage = "validated"
        return self.action_send_to_provider()

    def action_cancel(self):
        """Cancel the EDI document."""
        self.ensure_one()

        if self.processing_stage == "accepted" and self.provider_id:
            # Request cancellation from provider
            result = self.provider_id.cancel_document(self)

            if result.get("success"):
                self.write(
                    {
                        "processing_stage": "cancelled",
                        "state": "cancelled",
                    }
                )
            else:
                raise UserError(
                    _("Failed to cancel document with provider: %s")
                    % result.get("error")
                )
        else:
            self.write(
                {
                    "processing_stage": "cancelled",
                    "state": "cancelled",
                }
            )

        return True

    @api.model
    def _get_default_provider(self):
        """Get the default EDI provider for the current company."""
        return self.env["edi.provider"].search(
            [
                ("company_id", "=", self.move_id.company_id.id),
                ("is_default", "=", True),
            ],
            limit=1,
        )
