from odoo import models, fields


class TestModel(models.Model):
    _name = "test.model"

    name = fields.Char("Name")

    def action_test(self):
        pass
