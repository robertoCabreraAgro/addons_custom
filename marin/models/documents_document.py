from odoo import _, api, fields, models
from odoo.exceptions import UserError


class Documents(models.Model):
    _inherit = "documents.document"

    legal_number = fields.Char("Legal number")
    vehicle_id = fields.Many2one("fleet.vehicle", "Vehicle")

    @api.constrains("legal_number")
    def _check_duplicated_legal_number(self):
        for doc in self:
            overlap = self.env["documents.document"].search_count(
                [("id", "!=", doc.id), ("legal_number", "=", doc.legal_number)]
            )
            if overlap >= 1:
                raise UserError(
                    _('A document with legal number "%s - %s" already exists.', doc.display_name, doc.legal_number)
                )

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {}, legal_number=_("%s (copy)", self.legal_number))
        return super().copy(default=default)
