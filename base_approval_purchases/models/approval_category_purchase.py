from odoo import api, fields, models


class ApprovalCategoryPurchase(models.Model):
    """Approval categories specific for purchase orders."""
    _name = "approval.category.purchase"
    _description = "Purchase Approval Category"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char()
    sequence = fields.Integer()
    active = fields.Boolean()
    description = fields.Text()
    company_id = fields.Many2one()
    minimum_amount = fields.Monetary()
    maximum_amount = fields.Monetary()
    currency_id = fields.Many2one()
    approval_type = fields.Selection()
    approver_ids = fields.Many2many()

    def _check_purchase_amount_limits(self, amount):
        """Check if purchase amount falls within category limits."""
        pass

    def _get_required_approvers(self):
        """Get list of required approvers for this category."""
        pass