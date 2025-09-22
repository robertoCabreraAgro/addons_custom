from odoo import fields, models


class MrpReport(models.Model):
    _inherit = "mrp.report"

    production_type = fields.Char(
        readonly=True,
    )

    def _select(self):
        return (
            super()._select()
            + """,
            mo.production_type AS production_type
        """
        )

    def _group_by(self):
        return (
            super()._group_by()
            + """,
            mo.production_type
        """
        )
