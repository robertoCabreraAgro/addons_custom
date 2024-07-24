from odoo import models, fields


class PowerUserTip(models.Model):
    _name = "power.user.tip"
    _description = "Tips for queries"


    name = fields.Text(string="Query", required=True)
    tip_type = fields.Selection([
        ("python", "Python"),
        ("sql", "Postgresql")], "Type")
    description = fields.Text(string="Description", translate=True)
