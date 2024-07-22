from odoo import api, fields, models


class Documents(models.Model):
    _inherit = "documents.document"

    issued_by = fields.Many2one("res.partner", "Issued by", help="The authority that issued this licence")
    issued_date = fields.Date(help="The date on which this document was issued")
    expiration_date = fields.Date(
        help="The date on which this document will be expired. Leave it blank for non-expiration"
    )
    days_left = fields.Integer(
        "Days to expire", compute="_compute_days_left", help="The number of days to the expired date"
    )
    expired = fields.Boolean(default=False)

    @api.depends("expiration_date")
    def _compute_days_left(self):
        for record in self:
            if not record.expiration_date:
                record.days_left = 365
            else:
                today = fields.Date.today()
                record.days_left = (record.expiration_date - today).days

    def action_set_expired(self):
        self.write({"expired": True})

    def action_renew(self):
        self.write({"expired": False})

    def cron_find_and_set_expired(self):
        to_set_expired = self.search(
            [("expiration_date", "!=", False), ("expiration_date", "<=", fields.Date.today())]
        )
        if to_set_expired:
            to_set_expired.with_context(cron_mode=True).action_set_expired()
        return True
