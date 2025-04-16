# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    customer_last_order_date = fields.Datetime(string="Last order date", readonly=True)
    customer_last_order_ref = fields.Char(string="Last order reference", readonly=True)
