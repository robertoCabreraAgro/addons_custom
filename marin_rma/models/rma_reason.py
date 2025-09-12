from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class RmaReason(models.Model):
    _name = "rma.reason"
    _description = "RMA Reason"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    sequence = fields.Integer(string="Sequence")
    active = fields.Boolean(string="Active", default=True)

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            domain = [('name', '=', record.name), ('id', '!=', record.id)]
            existing_records = self.search(domain)
            if existing_records:
                raise ValidationError(_('The name “%s” already exists.', record.name))
