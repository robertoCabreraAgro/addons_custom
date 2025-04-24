from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = "res.partner"

    credit_status = fields.Selection(
        selection=[
            ("cash", "Cash Only"),
            ("review", "Under Review"),
            ("approved", "Credit Approved"),
            ("legal", "Legal Process"),
        ],
        string="Credit Status",
        compute="_compute_credit_status",
        tracking=True,
        store=True,
        help="""Partner's current credit authorization status: 

        • Cash Only: No credit allowed - Requires upfront payment. 
          Triggered when: New customers or those without assigned dossier 

        • Under Review: Credit temporarily suspended pending resolution  - Requires upfront payment. 
          Triggered when: Expired or missing documents, overdue invoices, or compliance issues detected.

        • Credit Approved: Full credit privileges granted.
          Achieved when: All documents valid, payment history clean, and requirements met.

        • Legal Process: All transactions blocked.
          Activated manually when: Legal disputes, collections process, or court orders.

        Status automatically updates when:
        - Documents are added/expire
        - Payment history changes
        - Dossier requirements are modified""",
    )

    dossier_id = fields.Many2one(
        comodel_name="res.partner.dossier",
        string="Credit Dossier",
        help="Credit requirements classification for this partner",
    )
    allowed_dossier_document_tag_ids = fields.Many2many(
        comodel_name="documents.tag",
        string="Allowed Document Tags",
        compute="_compute_allowed_dossier_document_tag_ids",
    )
    dossier_document_ids = fields.Many2many(
        comodel_name="documents.document",
        relation="partner_dossier_document_rel",
        column1="partner_id",
        column2="document_id",
        string="Dossier Documents",
        domain="[('partner_id', '=', id), ('tag_ids', 'in', allowed_dossier_document_tag_ids)]",
        help="Documents submitted for credit evaluation",
    )
    dossier_warning = fields.Text(
        string="Dossier Warning",
        compute="_compute_dossier_warning",
        store=True,
        help="Shows missing documents and compliance issues when reviewing dossier requirements",
    )
    trusted_amount = fields.Float(
        string="Trusted Amount",
        groups="account.group_account_invoice,account.group_account_readonly",
        company_dependent=True,
        copy=False,
        store=True,
        readonly=True,
        help="Additional amount added to the total guarantees provided",
    )
    credit_limit = fields.Float(
        compute="_compute_credit_limit",
        inverse="_inverse_credit_limit",
        groups="account.group_account_invoice,account.group_account_readonly",
        company_dependent=True,
        copy=False,
        store=True,
        readonly=False,
        tracking=True,
        help="Receivable limit specific to this partner.",
    )

    @api.depends_context("company")
    @api.depends(
        "dossier_id",
        "dossier_document_ids.collateral_amount",
        "trusted_amount",
    )
    def _compute_credit_limit(self):
        """Compute the credit limit for the partner based on their collateral documents and trust amount."""
        company_limit = self._fields["credit_limit"].get_company_dependent_fallback(
            self
        )

        for partner in self:
            credit_limit = company_limit

            # Check if partner has a dossier assigned
            if partner.dossier_id:

                # Sum all collateral amounts from documents with positive collateral value
                total_collateral = sum(
                    partner.dossier_document_ids.mapped("collateral_amount")
                )

                # Set computed credit limit: total collateral + trusted amount
                credit_limit = total_collateral + (partner.trusted_amount or 0.0)

            partner.credit_limit = credit_limit

    def _inverse_credit_limit(self):
        for partner in self:
            # Sum all collateral amounts from documents with positive collateral value
            total_collateral = sum(
                partner.dossier_document_ids.mapped("collateral_amount")
            )
            partner.trusted_amount = partner.credit_limit - total_collateral

    @api.depends("dossier_id.rule_ids.document_tag_id")
    def _compute_allowed_dossier_document_tag_ids(self):
        for partner in self:
            partner.allowed_dossier_document_tag_ids = (
                partner.dossier_id.rule_ids.mapped("document_tag_id")
            )

    def _get_credit_status(self):
        """Determine the credit status of a partner based on multiple criteria.

        The status is determined in the following order of priority:
        1. 'cash' - If the partner does not have a dossier
        2. 'review' - If the partner has a dossier warning or has overdue invoices
        3. 'approved' - If the partner passes all credit checks

        Returns:
            str: One of the following credit status values:
                - 'cash': Partner must pay in cash
                - 'review': Partner's credit needs review, but can pay in cash
                - 'approved': Partner is approved for credit
        """
        self.ensure_one()

        if not self.dossier_id:
            return "cash"
        if bool(self.dossier_warning) or self._has_overdue_invoices():
            return "review"
        return "approved"

    @api.depends(
        "dossier_id",
        "dossier_warning",
        "invoice_ids.invoice_date_due",
        "invoice_ids.payment_state",
        "invoice_ids.state",
    )
    def _compute_credit_status(self):
        """Compute partner's credit status based on:
        1. Legal process status (when forced via context)
        2. Document compliance with dossier requirements
        3. Document expiration status
        4. Payment history
        """
        for partner in self:
            if partner.credit_status == "legal":
                continue

            partner.credit_status = partner._get_credit_status()

    @api.depends(
        "dossier_id",
        "dossier_document_ids",
        "dossier_document_ids.tag_ids",
        "dossier_document_ids.expired",
        "dossier_document_ids.amount",
        "dossier_document_ids.collateral_amount",
        "dossier_document_ids.is_guarantor",
        "dossier_id.rule_ids",
    )
    def _compute_dossier_warning(self):
        """
        Compute field that evaluates document compliance and generates warning messages.
        Empty string means all requirements are met.
        """
        for partner in self:
            if not partner.dossier_id:
                partner.dossier_warning = False
                continue

            if not partner.dossier_document_ids:
                partner.dossier_warning = "No documents found in this partner's dossier"
                continue

            warning_messages = []
            rules_by_tag = defaultdict(list)

            # Organize rules by tag and guarantor status
            for rule in partner.dossier_id.rule_ids:
                rules_by_tag[(rule.document_tag_id.id, rule.is_guarantor)].append(rule)

            # Check for missing document types and quantity issues
            for (tag_id, is_guarantor), rules in rules_by_tag.items():
                matching_docs = partner.dossier_document_ids.filtered(
                    lambda d: tag_id in d.tag_ids.ids and d.is_guarantor == is_guarantor
                )

                for rule in rules:
                    # Check minimum quantity
                    if len(matching_docs) < rule.min_quantity:
                        tag_name = rule.document_tag_id.name
                        guarantor_text = " (Guarantor)" if is_guarantor else ""
                        warning_messages.append(
                            f"- Missing {tag_name}{guarantor_text} [Minimum {rule.min_quantity} required]"
                        )

                    # Check maximum quantity
                    if rule.max_quantity > 0 and len(matching_docs) > rule.max_quantity:
                        tag_name = rule.document_tag_id.name
                        warning_messages.append(
                            f"- Too many {tag_name} documents [Maximum {rule.max_quantity} allowed]"
                        )

            # Check document-level compliance issues
            for doc in partner.dossier_document_ids:
                doc_issues = []

                for tag in doc.tag_ids:
                    for rule in rules_by_tag.get((tag.id, doc.is_guarantor), []):
                        if rule.document_expires and doc.expired:
                            doc_issues.append(f"Expired")

                        if rule.requires_amount and not doc.amount:
                            doc_issues.append(f"Missing amount")

                        if (
                            rule.requires_collateral_amount
                            and not doc.collateral_amount
                        ):
                            doc_issues.append(f"Missing collateral amount")

                if doc_issues:
                    warning_messages.append(f"- '{doc.name}': {', '.join(doc_issues)}")

            partner.dossier_warning = (
                _("Compliance issues were found in the dossier:\n")
                + "\n".join(warning_messages)
                if warning_messages
                else False
            )

    def _has_overdue_invoices(self):
        """Check if partner has overdue invoices.
        Returns:
            bool: True if any invoice is overdue, False otherwise
        """
        self.ensure_one()
        return bool(
            self.env["account.move"].search_count(
                [
                    ("partner_id", "=", self.id),
                    ("move_type", "=", "out_invoice"),
                    ("payment_state", "not in", ["paid", "in_payment"]),
                    ("invoice_date_due", "<", fields.Date.today()),
                    ("state", "=", "posted"),
                ]
            )
        )

    def action_toggle_legal(self):
        """Toggle legal process status.

        When setting to legal, force the status. When removing legal status,
        recompute credit status with ignore_legal context.
        """
        self.ensure_one()
        credit_status = "legal"
        if self.credit_status == "legal":
            credit_status = self._get_credit_status()
        self.write({"credit_status": credit_status})

    def _validate_credit_checks(self, payment_term=None):
        """
        Check if the partner's credit status allows the requested operation.

        This method enforces credit status restrictions based on the partner's current
        status and the provided payment term. Users with specific permissions can
        bypass these restrictions.

        Args:
            payment_term (record): Payment term record, to determine if it's immediate payment
            user (record): User performing the action (defaults to current user)

        Returns:
            bool: True if the operation is allowed

        Raises:
            ValidationError: If the operation is not allowed based on credit status
        """
        self.ensure_one()

        # If no user provided, use current user
        credit_user = self._context.get("credit_user") or self.env.user

        # Check if user has permission to bypass credit validation
        allow_validate = credit_user.has_group(
            "partner_credit_checks.allow_to_validate_credit_checks"
        )
        if allow_validate:
            return True

        # Check for legal process - block all operations
        if self.credit_status == "legal":
            raise ValidationError(
                _(
                    f"Operations for partner '{self.name}' are blocked due to legal process in progress."
                )
            )

        # Check for immediate payment (cash)
        is_immediate_payment = payment_term and payment_term.is_immediate

        # If credit status is cash or review, only allow immediate payment
        if self.credit_status in ["cash", "review"]:
            if not is_immediate_payment:
                status_name = (
                    _("Cash Only")
                    if self.credit_status == "cash"
                    else _("Under Credit Review")
                )
                raise ValidationError(
                    _(
                        f"Partner '{self.name}' has credit status '{status_name}'. "
                        f"Only immediate payment terms are allowed."
                    )
                )

        return True

    def action_reset_trusted_amount(self):
        self.write({"trusted_amount": 0.0})
