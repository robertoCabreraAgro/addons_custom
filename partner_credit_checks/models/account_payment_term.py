from odoo import api, fields, models
from odoo.tools import float_round


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    is_immediate = fields.Boolean(
        string="Is Immediate Payment",
        compute="_compute_is_immediate",
        help="Indicates if this payment term requires immediate payment (single line, 100% amount, and 0 days due)",
    )

    @api.depends("line_ids.nb_days", "line_ids.value_amount", "line_ids.value")
    def _compute_is_immediate(self):
        """Compute whether the payment term is immediate (0 days, 100% payment, single line)."""
        for term in self:
            term.is_immediate = (
                len(term.line_ids) == 1
                and term.line_ids[0].nb_days == 0
                and term.line_ids[0].value == "percent"
                and float_round(term.line_ids[0].value_amount, precision_digits=2)
                == 100.0
            )
