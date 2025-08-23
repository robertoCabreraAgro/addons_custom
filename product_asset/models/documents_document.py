from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression


class Documents(models.Model):
    """Inherit Documents"""

    _inherit = "documents.document"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lot",
        compute="_compute_lot_id",
        search="_search_lot_id",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("res_id", "res_model")
    def _compute_lot_id(self):
        lot = self.env["stock.lot"]
        for document in self:
            document.lot_id = document.res_model == "stock.lot" and lot.browse(
                document.res_id
            )

    # ------------------------------------------------------------
    # SEARCH METHODS
    # ------------------------------------------------------------

    @api.model
    def _search_related_lot_field(self, operator, value, Model):
        if operator in ("=", "!=") and isinstance(value, bool):
            if not value:
                operator = expression.TERM_OPERATORS_NEGATION[operator]
            return [("res_model", operator, Model._name)]

        elif operator in ("=", "!=", "in", "not in") and isinstance(value, (int, list)):
            return expression.AND(
                [[("res_model", "=", Model._name)], [("res_id", operator, value)]]
            )

        elif operator in ("ilike", "not ilike", "=", "!=") and isinstance(value, str):
            query_model = Model._search([(Model._rec_name, operator, value)])
            query_doc = self._search(
                [("res_model", "=", Model._name), ("res_id", "in", query_model)]
            )
            return [("id", "in", query_doc)]

        raise ValidationError(
            _("Invalid %s search", self.env["ir.model"]._get(Model._name).name)
        )

    @api.model
    def _search_lot_id(self, operator, value):
        return self._search_related_lot_field(operator, value, self.env["stock.lot"])
