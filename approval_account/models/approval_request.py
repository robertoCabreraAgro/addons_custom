from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context
from odoo.tools.translate import _


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
    )
    count_account_move = fields.Integer(
        compute="_compute_count_account_move"
    )

    @api.depends("product_line_ids.account_move_id")
    def _compute_count_account_move(self):
        for request in self:
            moves = request.product_line_ids.account_move_id
            request.count_account_move = len(moves)

#    def action_confirm(self):
#        self._check_accounting_type_has_product()
#        return super().action_confirm()
#
#    def action_approve(self, approver=None):
#        self._check_accounting_type_has_product()
#        return super().action_approve(approver)

#    def action_cancel(self):
#        """Override to unlink the products of the cancelled Approval Request from Purchase Orders"""
#        res = super().action_cancel()
#        purchase_orders_data_per_state = self._cancel_approval_request()
#        self._log_po_cancellation_to_chatter(purchase_orders_data_per_state)
#        return res

#    def _cancel_approval_request(self):
#        purchase_orders = self.sudo().product_line_ids.purchase_order_line_id.order_id
#        purchase_orders_data_per_state = {"removed": [], "require_manual_action": []}
#        for purchase_order in purchase_orders:
#            product_lines = self.sudo().product_line_ids.filtered(
#                lambda line: line.purchase_order_line_id.order_id.id
#                == purchase_order.id
#            )
#
#            if purchase_order.state == "draft":
#                purchase_orders_data_per_state["removed"].extend(
#                    self._get_order_data_from_product_lines(product_lines)
#                )
#                removed_lines = self.sudo().env["account.move.line"]
#                for product_line in product_lines:
#                    purchase_order_line = product_line.purchase_order_line_id
#                    if purchase_order_line.product_qty == product_line.quantity:
#                        removed_lines |= purchase_order_line
#                    else:
#                        purchase_order_line.product_qty -= product_line.quantity
#                if len(purchase_order.order_line) == len(removed_lines):
#                    # Purchase orders must be canceled first before deletion
#                    purchase_order.write({"state": "cancel"})
#                    purchase_order.unlink()
#                elif removed_lines:
#                    removed_lines.unlink()
#
#            else:
#                purchase_orders_data_per_state["require_manual_action"].extend(
#                    self._get_order_data_from_product_lines(
#                        product_lines, include_raw_data=True
#                    )
#                )
#
#            product_lines.purchase_order_line_id = False
#
#        return purchase_orders_data_per_state

    def action_create_account_moves(self):
        self.ensure_one()
        self._create_account_moves()
        # self._log_po_creation_to_chatter()

    def _create_account_moves(self):
        for line in self.product_line_ids:
            new_account_move = self.env["account.move"].create(
                line._prepare_account_move_values_from_approval()
            )
            line.account_move_id = new_account_move.id

    def action_view_account_move(self):
        """Return the list of purchase orders the approval request created or
        affected in quantity."""
        self.ensure_one()
        move_ids = self.product_line_ids.account_move_id.ids
        domain = [("id", "in", move_ids)]
        action = {
            "name": _("Journal Entries"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_type": "list",
            "view_mode": "list,form",
            "context": clean_context(
                self.env.context
            ),  # avoid 'default_name' context key propagation
            "domain": domain,
        }
        return action

#    def _log_po_creation_to_chatter(self):
#        purchase_orders_data = self._get_order_data_from_product_lines(
#            self.product_line_ids
#        )
#        po_creation_chatter_msg = self._prepare_po_log_message(
#            "created", purchase_orders_data
#        )
#        self._message_log(body=po_creation_chatter_msg)

#    def _log_po_cancellation_to_chatter(self, purchase_orders_data_per_state):
#        po_cancellation_states = ["removed", "require_manual_action"]
#        cancellation_log_msg = ""
#        for po_state in po_cancellation_states:
#            purchase_orders_data = purchase_orders_data_per_state[po_state]
#            if purchase_orders_data:
#                cancellation_log_msg += self._prepare_po_log_message(
#                    po_state, purchase_orders_data
#                )
#            if po_state == "require_manual_action":
#                self._log_cancellation_exception_to_po_chatter(purchase_orders_data)
#        self._message_log(body=cancellation_log_msg)

#    def _log_cancellation_exception_to_po_chatter(self, purchase_orders_data):
#        for purchase_order_data in purchase_orders_data:
#            purchase_order_data["order"]._activity_schedule_with_view(
#                "mail.mail_activity_data_warning",
#                views_or_xmlid="approvals_purchase.exception_approval_request_canceled",
#                user_id=self.env.user.id,
#                render_context={
#                    "approval_requests": self,
#                    "product_lines": purchase_order_data["product_lines"],
#                },
#            )

#    def _get_order_data_from_product_lines(self, product_lines, include_raw_data=False):
#        """Returns a list of dictionaries, each representing the data of a single order.
#        Each dictionary has the following structure:
#        {
#            "order": The purchase order (optional)
#            "product_lines": The product lines of the approval request (optional)
#            "order_name": The name of the purchase order
#            "products": [(product_name, product_quantity), ...] A list of tuples. Each tuple contains product name and product quantity.
#        }"""
#        orders_data = list()
#        grouped_product_lines = product_lines.grouped(
#            lambda product_line: product_line.purchase_order_line_id.order_id
#        )
#        for order_id, lines in grouped_product_lines.items():
#            order_data = dict()
#            if include_raw_data:
#                order_data["order"] = order_id
#                order_data["product_lines"] = lines
#            order_data["order_name"] = order_id.name
#            order_data["products"] = [
#                (order_line.product_id.name, order_line.quantity)
#                for order_line in lines
#            ]
#            orders_data.append(order_data)
#        return orders_data

#    def _prepare_po_log_message(self, po_state, purchase_orders_data):
#        log_msg_header_by_state = {
#            "created": _("The following products have been added to the RFQs:"),
#            "removed": _("The following products have been removed from the RFQs:"),
#            "require_manual_action": _(
#                "The following products couldn't be removed because the RFQs are not in draft state:"
#            ),
#        }
#
#        return Markup("%(log_msg_header)s<br> <br> %(purchase_log)s <hr>") % {
#            "log_msg_header": log_msg_header_by_state.get(po_state, ""),
#            "purchase_log": Markup().join(
#                Markup("RFQ %(po_name)s: <br> <ul>%(products_lines)s</ul>")
#                % {
#                    "po_name": purchase_order["order_name"],
#                    "products_lines": Markup().join(
#                        Markup("<li>%(quantity)s %(name)s</li>")
#                        % {"name": product_line[0], "quantity": product_line[1]}
#                        for product_line in purchase_order["products"]
#                    ),
#                }
#                for purchase_order in purchase_orders_data
#            ),
#        }

    def _check_accounting_type_has_product(self):
        if (
            self.approval_type in (
                "entry",
                "in_invoice",
                "in_refund",
                "out_invoice",
                "out_refund",
            ) 
            and not self.product_line_ids
        ):
            raise UserError(
                _("You must select a product for each line of requested products.")
            )