from pytz import timezone

from odoo import fields, models

from .l10n_mx_edi_document import MXWS_ERROR_TYPE

DEFAULT_TZ = timezone("America/Mexico_City")


# pylint: disable=invalid-name
def str_to_datetime(dt_str, tz=DEFAULT_TZ):
    return tz.localize(fields.Datetime.from_string(dt_str))


class Session(models.Model):
    _name = "l10n_mx_edi.session"
    _description = "MX SAT session"

    name = fields.Date("Date", required=True, index=True, default=fields.Date.context_today)
    company_id = fields.Many2one("res.company", "Company", default=lambda self: self.env.company)
    uuid = fields.Char("UUID")
    token = fields.Char()
    token_expiration = fields.Datetime()
    date_from = fields.Datetime("Date from")
    date_to = fields.Datetime("Date to")
    request = fields.Char("Download request")
    request_status_code = fields.Char("Download request status code")
    request_state = fields.Selection(MXWS_ERROR_TYPE, "Request state")
    request_message = fields.Char("Request message")
    file_count = fields.Integer("File count")

    def get_mx_current_datetime(self):
        return fields.Datetime.context_timestamp(self.with_context(tz="America/Mexico_City"), fields.Datetime.now())
