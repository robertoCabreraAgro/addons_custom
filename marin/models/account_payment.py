from werkzeug.urls import url_quote_plus

from odoo import _, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    journal_type = fields.Selection(related="journal_id.type", string="Journal type", store=True, readonly=True)
    cash_transfer_pos_id = fields.Many2one("pos.session")
