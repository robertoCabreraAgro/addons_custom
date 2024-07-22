from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    property_sale_journal_id = fields.Many2one(
        "account.journal",
        "Default Sale Journal",
        company_dependent=True,
        check_company=True,
        domain="([('type', '=', 'sale')])",
    )

    def _get_default_sale_journal_id(self):
        if self.property_sale_journal_id:
            return self.property_sale_journal_id
        domain = [("company_id", "=", self.env.company.id), ("type", "=", "sale")]
        return self.env["account.journal"].search(domain, limit=1)

    # pylint: disable=invalid-name
    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["property_sale_journal_id"]

    # pylint: disable=invalid-name
    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["property_sale_journal_id"]
