from odoo import _, api, fields, models
from odoo.fields import Domain


class Documents(models.Model):
    """Extend document with asset linking capabilities."""

    _inherit = "documents.document"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Serial/Lot Number",
        compute="_compute_lot_id",
        search="_search_lot_id",
        index=True,
        help="Link to asset serial/lot number",
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
    def _search_lot_id(self, operator, value):
        return self._search_related_lot_field(operator, value, "stock.lot")

    @api.model
    def _search_related_lot_field(self, operator, value, field_name) -> Domain:
        assert field_name == "lot_id"
        Model = self.env[self._fields[field_name].comodel_name]
        if operator == "in":
            if True in value:
                # support for True value
                return (
                    Domain(field_name, "not in", [False])
                    | Domain(field_name, "in", value - {True})
                )
            if False in value:
                return (
                    Domain("res_model", "!=", Model._name)
                    | self._search_related_lot_field(
                        operator, value - {False}, field_name,
                    )
                )
            query_model = Model._search(
                Domain.OR(
                    Domain(Model._rec_name if isinstance(v, str) else "id", operator, v)
                    for v in value
                    if v
                ),
            )
        elif operator == "any" and isinstance(value, Domain):
            query_model = Model._search(value)
        elif operator.endswith("like") and not operator.startswith("not"):
            query_model = Model._search([(Model._rec_name, operator, value)])
        else:
            return NotImplemented
        return (
            Domain.FALSE
            if query_model.is_empty()
            else Domain("res_id", "in", query_model)
        ) & Domain("res_model", "=", Model._name)
