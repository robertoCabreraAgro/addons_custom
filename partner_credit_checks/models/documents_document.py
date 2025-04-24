from odoo import models, fields


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    amount = fields.Float(
        string="Amount", help="Amount for promissory notes, guarantees, contracts, etc."
    )
    collateral_amount = fields.Float(
        string="Collateral Amount", help="Collateral amount for guarantees"
    )
    is_guarantor = fields.Boolean(
        string="Is Guarantor", help="Indicates if this document acts as a guarantee"
    )

    dossier_compliance = fields.Boolean(
        string="Dossier Compliance",
        compute="_compute_dossier_compliance",
        help="Indicates whether the document complies with all partner dossier requirements",
    )

    def _compute_dossier_compliance(self):
        """
        Compute the document's compliance with partner dossier requirements.

        A document is considered compliant if:
        1. It belongs to a partner
        2. The partner has a dossier specified
        3. The document has at least one tag
        4. All document tags are in the partner's allowed tags
        5. For each tag, all matching rules (considering is_guarantor) are satisfied:
           - If document_expires is True, document must not be expired
           - If requires_amount is True, document must have amount
           - If requires_collateral_amount is True, document must have collateral_amount

        Rules only apply if their is_guarantor field matches the document's is_guarantor.
        """
        for doc in self:
            # Condition 1: Document must belong to a partner
            if not doc.partner_id:
                doc.dossier_compliance = False
                continue

            partner = doc.partner_id

            # Condition 2: Partner must have a dossier specified
            if not partner.dossier_id:
                doc.dossier_compliance = False
                continue

            # Condition 3: Document must have at least one tag
            if not doc.tag_ids:
                doc.dossier_compliance = False
                continue

            # Condition 4: All document tags must be in partner's allowed tags
            doc_tags = doc.tag_ids
            allowed_tags = partner.allowed_dossier_document_tag_ids
            if not any(tag in allowed_tags for tag in doc_tags):
                doc.dossier_compliance = False
                continue

            # Check rules for each document tag
            compliance = True
            dossier_rules = partner.dossier_id.rule_ids

            for tag in doc_tags:
                # Find rules that match both tag and is_guarantor status
                applicable_rules = dossier_rules.filtered(
                    lambda r: r.document_tag_id == tag
                    and r.is_guarantor == doc.is_guarantor
                )

                # If no rules for this tag+guarantor combination, skip
                if not applicable_rules:
                    continue

                for rule in applicable_rules:
                    # Check expiration requirement
                    if rule.document_expires and doc.expired:
                        compliance = False
                        break

                    # Check amount requirement
                    if rule.requires_amount and not doc.amount:
                        compliance = False
                        break

                    # Check collateral amount requirement
                    if rule.requires_collateral_amount and not doc.collateral_amount:
                        compliance = False
                        break

                if not compliance:
                    break

            doc.dossier_compliance = compliance

    def action_open_document(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }
