# -*- coding: utf-8 -*-
"""EDI-specific certificate extensions."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class EdiCertificate(models.Model):
    """EDI-specific certificate extensions."""

    _inherit = "certificate.certificate"

    # EDI-specific fields
    edi_scope = fields.Selection(
        [
            ("signing", "Document Signing"),
            ("encryption", "Encryption"),
            ("authentication", "Authentication"),
            ("all", "All Purposes"),
        ],
        string="EDI Usage Scope",
        default="signing",
        help="The purpose for which this certificate is used in EDI operations",
    )

    issuer_type = fields.Selection(
        [
            ("government", "Government Authority"),
            ("accredited", "Accredited Provider"),
            ("private", "Private CA"),
            ("self_signed", "Self-Signed"),
        ],
        string="Issuer Type",
        help="Type of certificate issuer",
    )

    edi_country_code = fields.Char(
        string="EDI Country",
        size=2,
        help="Country code for which this certificate is valid in EDI context",
    )

    # Validation status
    edi_validation_status = fields.Selection(
        [
            ("not_validated", "Not Validated"),
            ("valid", "Valid"),
            ("invalid", "Invalid"),
            ("expired", "Expired"),
        ],
        string="EDI Validation Status",
        compute="_compute_edi_validation_status",
        store=True,
    )

    edi_validation_message = fields.Text(
        string="Validation Message",
        compute="_compute_edi_validation_status",
        store=True,
    )

    # Usage tracking
    last_used_date = fields.Datetime(
        string="Last Used",
        help="Last time this certificate was used for EDI operations",
    )

    usage_count = fields.Integer(
        string="Usage Count",
        default=0,
        help="Number of times this certificate has been used",
    )

    # Related documents
    edi_document_ids = fields.One2many(
        "account.edi.document",
        "certificate_id",
        string="EDI Documents",
        help="EDI documents signed with this certificate",
    )

    edi_document_count = fields.Integer(
        string="Document Count", compute="_compute_edi_document_count"
    )

    @api.depends("is_valid", "date_end", "edi_country_code")
    def _compute_edi_validation_status(self):
        """Compute EDI validation status."""
        for cert in self:
            if not cert.is_valid:
                if cert.date_end and cert.date_end < datetime.now():
                    cert.edi_validation_status = "expired"
                    cert.edi_validation_message = _("Certificate has expired")
                else:
                    cert.edi_validation_status = "invalid"
                    cert.edi_validation_message = _("Certificate is not valid")
            else:
                # Perform EDI-specific validations
                validation_result = cert.validate_for_edi()
                if validation_result[0]:
                    cert.edi_validation_status = "valid"
                    cert.edi_validation_message = validation_result[1]
                else:
                    cert.edi_validation_status = "invalid"
                    cert.edi_validation_message = validation_result[1]

    @api.depends("edi_document_ids")
    def _compute_edi_document_count(self):
        """Compute the count of EDI documents."""
        for cert in self:
            cert.edi_document_count = len(cert.edi_document_ids)

    def validate_for_edi(self, country_code=None):
        """
        Validate certificate for EDI usage.

        Args:
            country_code (str): Optional country code for country-specific validation

        Returns:
            tuple: (is_valid, message)
        """
        self.ensure_one()

        # Check basic validity
        if not self.is_valid:
            return False, _("Certificate is not valid or has expired")

        # Check EDI country if specified
        if country_code and self.edi_country_code:
            if self.edi_country_code != country_code:
                return False, _("Certificate is for country %s, not %s") % (
                    self.edi_country_code,
                    country_code,
                )

        # Check if certificate has necessary components
        if self.edi_scope in ("signing", "all") and not self.private_key_id:
            return False, _("Certificate lacks private key for signing")

        # Additional validations can be added by country-specific modules
        return True, _("Certificate is valid for EDI operations")

    def action_validate_edi(self):
        """Action to validate certificate for EDI."""
        self.ensure_one()

        is_valid, message = self.validate_for_edi()

        if is_valid:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Certificate Valid"),
                    "message": message,
                    "type": "success",
                    "sticky": False,
                },
            }
        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Certificate Invalid"),
                    "message": message,
                    "type": "danger",
                    "sticky": True,
                },
            }

    def get_signature_algorithm(self):
        """
        Get the signature algorithm for this certificate.

        Returns:
            str: Signature algorithm name (e.g., 'RSA-SHA256')
        """
        self.ensure_one()

        # This would be extracted from the certificate
        # For now, return a default
        return "RSA-SHA256"

    def track_usage(self):
        """Track the usage of this certificate."""
        self.ensure_one()

        self.sudo().write(
            {
                "last_used_date": fields.Datetime.now(),
                "usage_count": self.usage_count + 1,
            }
        )

    def action_view_edi_documents(self):
        """View EDI documents signed with this certificate."""
        self.ensure_one()

        return {
            "name": _("EDI Documents"),
            "type": "ir.actions.act_window",
            "res_model": "account.edi.document",
            "view_mode": "tree,form",
            "domain": [("certificate_id", "=", self.id)],
            "context": {"default_certificate_id": self.id},
        }

    @api.model
    def get_edi_certificate(self, company, country_code=None, scope="signing"):
        """
        Get a valid EDI certificate for the given criteria.

        Args:
            company (res.company): Company to get certificate for
            country_code (str): Optional country code
            scope (str): EDI scope required

        Returns:
            certificate.certificate: Valid certificate or False
        """
        domain = [
            ("company_id", "=", company.id),
            ("is_valid", "=", True),
        ]

        if country_code:
            domain.append(("edi_country_code", "=", country_code))

        if scope:
            domain.append(("edi_scope", "in", (scope, "all")))

        certificates = self.search(domain, order="date_end desc")

        # Return the certificate with the longest validity
        return certificates[:1] if certificates else False
