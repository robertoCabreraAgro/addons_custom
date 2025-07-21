import base64
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    x_check_tax = fields.Monetary(
        string="Verification tax",
        copy=False,
    )
    x_check_total = fields.Monetary(
        string="Verification total",
        copy=False,
    )
    x_tax_difference = fields.Monetary(
        string="Tax difference",
        compute="_compute_x_difference",
    )
    x_total_difference = fields.Monetary(
        string="Total difference",
        compute="_compute_x_difference",
    )

    @api.depends("amount_tax", "amount_total", "x_check_tax", "x_check_total")
    def _compute_x_difference(self):
        for move in self:
            move.x_tax_difference = 0.0
            move.x_total_difference = 0.0
            if move.x_check_tax:
                move.x_tax_difference = float_round(
                    move.x_check_tax - move.amount_tax,
                    precision_rounding=move.currency_id.rounding,
                )
            if move.x_check_total:
                move.x_total_difference = float_round(
                    move.x_check_total - move.amount_total,
                    precision_rounding=move.currency_id.rounding,
                )

    def _extract_uuid_from_attachments(self):
        """Extract UUID from XML attachments of the invoice if it doesn't have one assigned.

        This method searches for XML attachments in purchase invoices without UUID,
        attempts to extract the UUID from valid CFDI files, checks for duplicates,
        and assigns the UUID if valid.

        Returns:
            bool: True if a valid UUID was found and assigned, False otherwise.
        """
        mx_edi_document = self.env["l10n_mx_edi.document"]

        for move in self:
            # Only process purchase documents without UUID
            if not move.is_purchase_document() or move.l10n_mx_edi_cfdi_uuid:
                continue

            # Search for XML attachments
            xml_attachments = self.env["ir.attachment"].search(
                [
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", move.id),
                    "|",
                    ("mimetype", "in", ["text/xml", "application/xml"]),
                    ("name", "ilike", ".xml"),
                ]
            )

            for attachment in xml_attachments:
                try:
                    xml_content = base64.b64decode(attachment.datas)
                    cfdi_infos = mx_edi_document._decode_cfdi_attachment(xml_content)

                    if not cfdi_infos or not cfdi_infos.get("uuid"):
                        continue

                    # Check for UUID duplication before assignment
                    duplicity_result = mx_edi_document._get_duplicate_cfdi(
                        cfdi_infos["uuid"], move
                    )

                    if duplicity_result["duplicated"]:
                        # If duplicated, notify but continue searching
                        self.env["bus.bus"]._sendone(
                            self.env.user.partner_id,
                            "simple_notification",
                            {
                                "title": "Duplicated CFDI UUID",
                                "message": duplicity_result["message"],
                                "sticky": False,
                                "warning": True,
                            },
                        )
                        continue

                    # Assign UUID to the invoice
                    move.with_context(no_validate_uuid=True).write(
                        {"l10n_mx_edi_cfdi_uuid": cfdi_infos["uuid"]}
                    )
                    _logger.info(
                        "UUID %s extracted and assigned to invoice %s",
                        cfdi_infos["uuid"],
                        move.name,
                    )

                    # Stop after finding the first valid UUID
                    return True

                except Exception as e:
                    _logger.warning(
                        "Failed to extract UUID from XML attachment %s: %s",
                        attachment.name,
                        str(e),
                    )
                    continue

        return False

    def _post(self, soft=True):
        """Override of the _post method to validate UUID when required.

        This implementation:
        1. Attempts to extract UUID from attached XMLs when the journal requires UUID
           and the invoice doesn't have one
        2. Validates that invoices have UUID when the journal requires it
        3. Checks that the UUID is not duplicated

        Args:
            soft (bool): If True, performs a soft post (draft post)

        Returns:
            bool: Result of the parent _post method

        Raises:
            ValidationError: If UUID is missing when required or if UUID is duplicated
        """
        # Extract UUID and validate only for purchase invoices about to be posted
        for move in self.filtered(
            lambda m: m.is_purchase_document() and m.state == "draft"
        ):
            # Try to extract UUID from attachments if missing
            if not move.l10n_mx_edi_cfdi_uuid:
                move._extract_uuid_from_attachments()

            # Validate UUID presence if required by journal
            if (
                not move.l10n_mx_edi_cfdi_uuid
                and move.journal_id.l10n_mx_edi_require_uuid
            ):
                raise ValidationError(
                    self.env._(
                        "Invoice %s cannot be posted. This journal requires a CFDI UUID because its treatment is set as fiscal.",
                        move.name,
                    )
                )

            # Check for UUID duplication
            if move.l10n_mx_edi_cfdi_uuid:
                duplicity_result = self.env["l10n_mx_edi.document"]._get_duplicate_cfdi(
                    move.l10n_mx_edi_cfdi_uuid, move
                )

                if duplicity_result["duplicated"]:
                    raise ValidationError(duplicity_result["message"])

        return super()._post(soft=soft)
