from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


class Documents(models.Model):
    _inherit = "documents.document"

    legal_number = fields.Char("Legal number")
    vehicle_id = fields.Many2one("fleet.vehicle", "Vehicle", compute="_compute_vehicle", search="_search_vehicle_id")

    @api.depends("res_id", "res_model")
    def _compute_vehicle(self):
        Vehicle = self.env["fleet.vehicle"]
        for document in self:
            document.vehicle_id = document.res_model == "fleet.vehicle" and Vehicle.browse(document.res_id)

    @api.model
    def _search_vehicle_id(self, operator, value):
        return self._search_related_vehicle_field(operator, value, self.env["fleet.vehicle"])

    @api.model
    def _search_related_vehicle_field(self, operator, value, Model):
        if operator in ('=', '!=') and isinstance(value, bool):
            if not value:
                operator = expression.TERM_OPERATORS_NEGATION[operator]
            return [("res_model", operator, Model._name)]
        elif operator in ('=', '!=', "in", "not in") and isinstance(value, (int, list)):
            return expression.AND([[("res_model", "=", Model._name)], [("res_id", operator, value)]])
        elif operator in ("ilike", "not ilike", "=", "!=") and isinstance(value, str):
            query_model = Model._search([(Model._rec_name, operator, value)])
            query_doc = self._search([('res_model', '=', Model._name), ('res_id', 'in', query_model)])
            return [("id", "in", query_doc)]
        raise ValidationError(_("Invalid %s search", self.env['ir.model']._get(Model._name).name))

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
