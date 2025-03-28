from odoo import fields, models
from odoo.fields import Command


class ApprovalProductLine(models.Model):
    _inherit = "approval.product.line"

    product_id = fields.Many2one(
        domain=lambda self: self._get_product_id_domain(),
    )
    purchase_order_line_id = fields.Many2one(
        comodel_name="purchase.order.line",
    )
    account_move_id = fields.Many2one(
        comodel_name="account.move",
    )

    def _get_product_id_domain(self):
        """Filters on product to get only the ones who are available on
        purchase in the case the approval request type is purchase."""
        # TODO: How to manage this when active model isn't approval.category ?
        if "default_category_id" in self.env.context:
            category_id = self.env.context.get("default_category_id")
        elif self.env.context.get("active_model") == "approval.category":
            category_id = self.env.context.get("active_id")
        else:
            return []

        category = self.env["approval.category"].browse(category_id)
        if category.approval_type == "purchase":
            return [("purchase_ok", "=", True)]

    def _get_purchase_order_line_for_approval_matching_domain(self):
        """Return a domain to get purchase order(s) where this product line could fit in.

        :return: list of tuple."""
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "draft"),
            ("product_id", "=", self.product_id.id),
            ("product_uom_id", "=", self.product_uom_id.id),
        ]
        return domain

    def _prepare_purchase_order_values_from_approval(self):
        """Get some values used to create a purchase order.
        Called in approval.request `action_create_purchase_orders`.

        :param vendor: a res.partner record
        :return: dict of values"""
        self.ensure_one()
        vals = {
            "company_id": self.company_id.id,
            "partner_id": self.partner_id.id,
            "payment_term_id": self.partner_id.property_supplier_payment_term_id.id,
            "fiscal_position_id": self.env["account.fiscal.position"]
            ._get_fiscal_position(self.partner_id)
            .id,
            "origin": self.approval_request_id.name,
            "order_line_ids": [
                Command.create(
                    {
                        "product_id": self.product_id.id,
                        "product_uom_id": self.product_uom_id.id,
                        "product_qty": self.quantity,
                    },
                )
            ],
        }
        return vals

    def _prepare_account_move_values_from_approval(self):
        """Get some values used to create a journal_entryr.
        Called in approval.request `action_create_account_move`.

        :param vendor: a res.partner record
        :return: dict of values"""
        self.ensure_one()

        vals = {
            "company_id": self.company_id.id,
            "journal_id": self.approval_request_id.journal_id.id,
            "partner_id": self.approval_request_id.partner_id.id,
            "invoice_payment_term_id": self.approval_request_id.partner_id.property_supplier_payment_term_id.id,
            "move_type": self.approval_request_id.approval_type,
            "line_ids": [
                Command.create(
                    {
                        "product_id": self.product_id.id,
                        "product_uom_id": self.product_uom_id.id,
                        "quantity": self.quantity,
                        "price_unit": self.price_unit,
                    },
                )
            ],
        }
        return vals
