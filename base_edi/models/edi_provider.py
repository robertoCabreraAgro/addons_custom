# -*- coding: utf-8 -*-
"""Web service provider abstraction for EDI operations."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
from abc import abstractmethod

_logger = logging.getLogger(__name__)


class EdiProvider(models.Model):
    """EDI service provider abstraction."""

    _name = "edi.provider"
    _description = "EDI Provider"
    _order = "sequence, name"

    name = fields.Char(string="Provider Name", required=True)
    code = fields.Char(string="Provider Code", required=True, index=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    is_default = fields.Boolean(
        string="Default Provider", help="Default provider for this company"
    )

    # Provider type and capabilities
    provider_type = fields.Selection(
        [
            ("direct", "Direct to Authority"),
            ("intermediary", "Intermediary Service"),
            ("hybrid", "Hybrid"),
        ],
        string="Provider Type",
        default="intermediary",
    )

    supports_signing = fields.Boolean(string="Supports Signing", default=True)
    supports_cancellation = fields.Boolean(string="Supports Cancellation", default=True)
    supports_status_check = fields.Boolean(string="Supports Status Check", default=True)
    supports_batch = fields.Boolean(string="Supports Batch Processing", default=False)

    # Connection settings
    base_url = fields.Char(string="Base URL")
    sign_url = fields.Char(string="Signing Endpoint")
    cancel_url = fields.Char(string="Cancellation Endpoint")
    status_url = fields.Char(string="Status Check Endpoint")

    username = fields.Char(string="Username")
    password = fields.Char(string="Password")
    api_key = fields.Char(string="API Key")
    api_secret = fields.Char(string="API Secret")

    test_mode = fields.Boolean(string="Test Mode", help="Use test/sandbox environment")

    timeout = fields.Integer(
        string="Timeout (seconds)", default=30, help="Request timeout in seconds"
    )

    # Statistics
    last_connection = fields.Datetime(string="Last Connection")
    connection_status = fields.Selection(
        [
            ("connected", "Connected"),
            ("error", "Error"),
            ("not_tested", "Not Tested"),
        ],
        string="Connection Status",
        default="not_tested",
    )

    error_message = fields.Text(string="Last Error")

    # Supported formats
    supported_format_ids = fields.Many2many(
        "account.edi.format", string="Supported Formats"
    )

    @api.constrains("is_default")
    def _check_single_default(self):
        """Ensure only one default provider per company."""
        for provider in self:
            if provider.is_default:
                other_defaults = self.search(
                    [
                        ("company_id", "=", provider.company_id.id),
                        ("is_default", "=", True),
                        ("id", "!=", provider.id),
                    ]
                )
                if other_defaults:
                    raise UserError(
                        _("There can only be one default provider per company")
                    )

    def get_headers(self):
        """
        Get HTTP headers for API requests.

        Returns:
            dict: HTTP headers
        """
        self.ensure_one()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.api_key:
            headers["X-API-Key"] = self.api_key

        return headers

    def get_auth(self):
        """
        Get authentication for requests.

        Returns:
            tuple or None: Authentication credentials
        """
        self.ensure_one()

        if self.username and self.password:
            return (self.username, self.password)

        return None

    def make_request(self, method, endpoint, data=None, files=None):
        """
        Make HTTP request to provider.

        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint
            data (dict): Request data
            files (dict): Files to upload

        Returns:
            dict: Response data
        """
        self.ensure_one()

        url = f"{self.base_url}/{endpoint}".replace("//", "/")

        try:
            response = requests.request(
                method=method,
                url=url,
                json=data,
                files=files,
                headers=self.get_headers(),
                auth=self.get_auth(),
                timeout=self.timeout,
            )

            response.raise_for_status()

            self.sudo().write(
                {
                    "last_connection": fields.Datetime.now(),
                    "connection_status": "connected",
                    "error_message": False,
                }
            )

            return response.json() if response.text else {}

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            _logger.error("Provider %s request failed: %s", self.name, error_msg)

            self.sudo().write(
                {
                    "last_connection": fields.Datetime.now(),
                    "connection_status": "error",
                    "error_message": error_msg,
                }
            )

            raise UserError(_("Provider communication failed: %s") % error_msg)

    def send_document(self, document):
        """
        Send EDI document to provider.

        Args:
            document (account.edi.document): Document to send

        Returns:
            dict: Result with 'success' and other fields
        """
        self.ensure_one()

        if not self.supports_signing:
            raise UserError(
                _("Provider %s does not support document signing") % self.name
            )

        # This is a base implementation - specific providers will override
        _logger.info("Sending document %s to provider %s", document.id, self.name)

        # Placeholder implementation
        return {
            "success": True,
            "tracking_id": f"TRACK-{document.id}",
            "response": "Document sent successfully",
        }

    def cancel_document(self, document):
        """
        Cancel EDI document with provider.

        Args:
            document (account.edi.document): Document to cancel

        Returns:
            dict: Result with 'success' and other fields
        """
        self.ensure_one()

        if not self.supports_cancellation:
            raise UserError(_("Provider %s does not support cancellation") % self.name)

        # This is a base implementation - specific providers will override
        _logger.info("Cancelling document %s with provider %s", document.id, self.name)

        # Placeholder implementation
        return {
            "success": True,
            "response": "Document cancelled successfully",
        }

    def check_document_status(self, document):
        """
        Check EDI document status with provider.

        Args:
            document (account.edi.document): Document to check

        Returns:
            dict: Status information
        """
        self.ensure_one()

        if not self.supports_status_check:
            raise UserError(
                _("Provider %s does not support status checking") % self.name
            )

        # This is a base implementation - specific providers will override
        _logger.info("Checking status for document %s", document.id)

        # Placeholder implementation
        return {
            "status": "valid",
            "message": "Document is valid",
        }

    def test_connection(self):
        """Test connection to provider."""
        self.ensure_one()

        try:
            # Make a test request
            # This would be implemented based on provider's test endpoint
            self.make_request("GET", "test" if not self.test_mode else "test/sandbox")

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Successful"),
                    "message": _("Successfully connected to %s") % self.name,
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Failed"),
                    "message": str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }
