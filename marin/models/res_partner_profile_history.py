from odoo import api, fields, models


class ResPartnerProfileHistory(models.Model):
    _name = "res.partner.profile.history"
    _description = "Partner Profile History"
    _order = "change_date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        ondelete="cascade",
    )
    change_date = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
    )
    old_profile_id = fields.Many2one(
        comodel_name="res.partner.profile",
    )
    new_profile_id = fields.Many2one(
        comodel_name="res.partner.profile",
        required=True,
    )
    old_score_total = fields.Float()
    new_score_total = fields.Float()
    score_hectares = fields.Float()
    score_categories = fields.Float()
    change_trigger = fields.Selection(
        selection=[
            ("manual", "Manual Assignment"),
            ("hectares", "Hectares Change"),
            ("category", "Category Change"),
            ("scoring", "Scoring Update"),
        ],
        required=True,
    )
    change_reason = fields.Text()
    user_id = fields.Many2one(
        comodel_name="res.users",
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        related="partner_id.company_id",
        comodel_name="res.company",
        store=True,
    )

    @api.depends("partner_id", "old_profile_id", "new_profile_id", "change_date")
    def _compute_display_name(self):
        for record in self:
            if record.partner_id and record.new_profile_id:
                old_name = (
                    record.old_profile_id.name if record.old_profile_id else "None"
                )
                new_name = record.new_profile_id.name
                date_str = (
                    record.change_date.strftime("%Y-%m-%d %H:%M")
                    if record.change_date
                    else ""
                )
                record.display_name = (
                    f"{record.partner_id.name}: "
                    f"{old_name} → {new_name} ({date_str})"
                )
            else:
                record.display_name = "Profile Change"
