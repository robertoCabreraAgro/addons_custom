from odoo import _, models


class Documents(models.Model):
    """Inherit Documents"""

    _inherit = "documents.document"

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {}, legal_number=_("%s (copy)", self.legal_number))
        return super().copy(default=default)

