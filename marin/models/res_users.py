from odoo import fields, models


class ResUsers(models.Model):
    """Inherit ResUsers"""

    _inherit = "res.users"

    property_purchase_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Default Purchase Journal",
        company_dependent=True,
        check_company=True,
        domain="([('type', '=', 'purchase')])",
    )
    property_sale_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Default Sale Journal",
        company_dependent=True,
        check_company=True,
        domain="([('type', '=', 'sale')])",
    )
    season_id = fields.Many2one(
        comodel_name="date.range",
        string="AG Season",
        domain="[('type_id.name', '=', 'AG Season')]",
        help="Default AG season for this user's sales orders",
    )

    def _get_default_purchase_journal_id(self):
        if self.property_purchase_journal_id:
            return self.property_purchase_journal_id

        domain = [("company_id", "=", self.env.company.id), ("type", "=", "purchase")]
        return self.env["account.journal"].search(domain, limit=1)

    def _get_default_sale_journal_id(self):
        if self.property_sale_journal_id:
            return self.property_sale_journal_id

        domain = [("company_id", "=", self.env.company.id), ("type", "=", "sale")]
        return self.env["account.journal"].search(domain, limit=1)

    # pylint: disable=invalid-name
    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            "property_purchase_journal_id",
            "property_sale_journal_id",
            "season_id",
        ]

    # pylint: disable=invalid-name
    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            "property_purchase_journal_id",
            "property_sale_journal_id",
            "season_id",
        ]
