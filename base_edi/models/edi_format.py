# -*- coding: utf-8 -*-
"""Enhanced EDI format base."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import etree
import base64
import logging

_logger = logging.getLogger(__name__)


class EdiFormat(models.AbstractModel):
    """Enhanced EDI format base for country-specific implementations."""

    _name = "base.edi.format"
    _inherit = "account.edi.format"
    _description = "Base EDI Format"

    # Format metadata
    version = fields.Char(
        string="Format Version", help="Version of this EDI format (e.g., 3.3, 4.0)"
    )

    country_code = fields.Char(
        string="Country Code", size=2, help="ISO 3166-1 alpha-2 country code"
    )

    document_type = fields.Selection(
        [
            ("invoice", "Invoice"),
            ("credit_note", "Credit Note"),
            ("debit_note", "Debit Note"),
            ("payment", "Payment"),
            ("payroll", "Payroll"),
            ("waybill", "Waybill"),
            ("receipt", "Receipt"),
        ],
        string="Document Type",
        default="invoice",
    )

    # Validation rules
    xsd_schema = fields.Binary(
        string="XSD Schema", help="XSD schema file for XML validation"
    )

    xsd_schema_filename = fields.Char(string="XSD Schema Filename")

    schematron_rules = fields.Binary(
        string="Schematron Rules",
        help="Additional validation rules in Schematron format",
    )

    schematron_filename = fields.Char(string="Schematron Filename")

    # Provider configuration
    requires_provider = fields.Boolean(
        string="Requires Provider",
        help="Whether this format requires an EDI provider for processing",
    )

    supported_providers = fields.Many2many(
        "edi.provider",
        string="Supported Providers",
        help="EDI providers that support this format",
    )

    # Feature flags
    supports_batch = fields.Boolean(
        string="Supports Batch Processing",
        default=True,
        help="Whether multiple documents can be processed together",
    )

    supports_async = fields.Boolean(
        string="Supports Async Processing",
        default=True,
        help="Whether documents can be processed asynchronously",
    )

    requires_signature = fields.Boolean(
        string="Requires Digital Signature",
        help="Whether documents in this format must be digitally signed",
    )

    # Template configuration
    template_id = fields.Many2one(
        "ir.ui.view",
        string="XML Template",
        help="QWeb template for generating XML content",
    )

    def _validate_against_schema(self, xml_content):
        """
        Validate XML content against XSD schema.

        Args:
            xml_content (bytes): XML content to validate

        Returns:
            tuple: (is_valid, error_messages)
        """
        self.ensure_one()

        if not self.xsd_schema:
            return True, []

        try:
            # Parse XML
            xml_doc = etree.fromstring(xml_content)

            # Load XSD schema
            xsd_content = base64.b64decode(self.xsd_schema)
            xsd_doc = etree.fromstring(xsd_content)
            schema = etree.XMLSchema(xsd_doc)

            # Validate
            if schema.validate(xml_doc):
                return True, []
            else:
                errors = [str(error) for error in schema.error_log]
                return False, errors

        except Exception as e:
            _logger.exception("Schema validation failed")
            return False, [str(e)]

    def _validate_against_schematron(self, xml_content):
        """
        Validate XML content against Schematron rules.

        Args:
            xml_content (bytes): XML content to validate

        Returns:
            tuple: (is_valid, error_messages)
        """
        self.ensure_one()

        if not self.schematron_rules:
            return True, []

        # Schematron validation would be implemented here
        # This is a placeholder
        return True, []

    def _get_format_requirements(self):
        """
        Get the requirements for this EDI format.

        Returns:
            dict: Dictionary of requirements
        """
        self.ensure_one()

        return {
            "requires_signature": self.requires_signature,
            "requires_provider": self.requires_provider,
            "country_code": self.country_code,
            "document_types": self.document_type,
            "version": self.version,
        }

    def _check_move_compatibility(self, move):
        """
        Check if a move is compatible with this EDI format.

        Args:
            move (account.move): The move to check

        Returns:
            bool: True if compatible, False otherwise
        """
        self.ensure_one()

        # Check country
        if self.country_code and move.company_id.country_id.code != self.country_code:
            return False

        # Check document type
        if self.document_type:
            move_type_mapping = {
                "out_invoice": "invoice",
                "in_invoice": "invoice",
                "out_refund": "credit_note",
                "in_refund": "credit_note",
            }

            if move_type_mapping.get(move.move_type) != self.document_type:
                return False

        return True

    def _generate_document_content(self, move):
        """
        Generate EDI document content for a move.

        Args:
            move (account.move): The move to generate content for

        Returns:
            bytes: Generated document content
        """
        self.ensure_one()

        if not self.template_id:
            raise ValidationError(
                _("No template configured for EDI format %s") % self.name
            )

        # Prepare values for template
        template_values = self._prepare_template_values(move)

        # Render template
        content = self.env["ir.qweb"]._render(self.template_id.id, template_values)

        # Validate if schemas are configured
        if self.xsd_schema:
            is_valid, errors = self._validate_against_schema(content)
            if not is_valid:
                raise ValidationError(
                    _("XML validation failed:\n%s") % "\n".join(errors)
                )

        return content

    def _prepare_template_values(self, move):
        """
        Prepare values for template rendering.
        To be overridden by specific implementations.

        Args:
            move (account.move): The move to prepare values for

        Returns:
            dict: Template values
        """
        return {
            "move": move,
            "company": move.company_id,
            "partner": move.partner_id,
            "format": self,
            "datetime": fields.Datetime,
            "date": fields.Date,
        }

    def _get_batch_key(self, move):
        """
        Get the batch key for a move.
        Documents with the same batch key can be processed together.

        Args:
            move (account.move): The move to get batch key for

        Returns:
            tuple: Batch key
        """
        self.ensure_one()

        if not self.supports_batch:
            # Each document in its own batch
            return (self.id, move.id)

        # Default batching by format, company, and move type
        return (
            self.id,
            move.company_id.id,
            move.move_type,
            move.partner_id.id if move.partner_id else False,
        )

    @api.model
    def _register_format(self, code, name, **kwargs):
        """
        Helper method to register a new EDI format.

        Args:
            code (str): Unique code for the format
            name (str): Display name for the format
            **kwargs: Additional fields for the format
        """
        existing = self.search([("code", "=", code)], limit=1)

        if existing:
            existing.write(kwargs)
            return existing
        else:
            return self.create({"code": code, "name": name, **kwargs})
