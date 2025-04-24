# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PartnerDossierRule(models.Model):
    """Partner Dossier Rule"""

    _name = "res.partner.dossier.rule"
    _description = "Partner Dossier Rule"

    name = fields.Char(string="Name", required=True)

    document_tag_id = fields.Many2one(
        comodel_name="documents.tag",
        string="Document Tag",
        required=True,
        help="Document type required for this rule",
    )

    document_expires = fields.Boolean(
        string="Document Expires",
        help="Check if documents for this rule have expiration dates",
    )

    is_guarantor = fields.Boolean(
        string="Is Guarantor", help="Indicates if this rule is for guarantor documents"
    )

    requires_amount = fields.Boolean(
        string="Requires Amount",
        help="Check if documents for this rule must include an amount",
    )

    requires_collateral_amount = fields.Boolean(
        string="Requires Collateral Amount",
        help="Check if documents for this rule must include a collateral amount",
    )

    min_quantity = fields.Integer(
        string="Minimum Quantity",
        default=0,
        help="Minimum number of required documents (0 means not required)",
    )

    max_quantity = fields.Integer(
        string="Maximum Quantity",
        default=0,
        help="Maximum number of allowed documents (0 means unlimited)",
    )

    dossier_id = fields.Many2one(
        comodel_name="res.partner.dossier", string="Dossier", ondelete="cascade"
    )

    @api.constrains("min_quantity", "max_quantity")
    def _check_quantity_constraints(self):
        """Validate that max quantity is not less than min quantity when both are set."""
        for rule in self:
            if rule.max_quantity > 0 and rule.min_quantity > rule.max_quantity:
                raise ValidationError(
                    "Minimum quantity cannot be greater than maximum quantity"
                )
