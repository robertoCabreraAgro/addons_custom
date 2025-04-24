# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PartnerDossier(models.Model):
    """Partner Credit Dossier Type"""

    _name = "res.partner.dossier"
    _description = "Partner Credit Dossier Type"

    name = fields.Char(translate=True)
    description = fields.Text(translate=True)
    active = fields.Boolean(string="Active", default=True)
    rule_ids = fields.One2many(
        comodel_name="res.partner.dossier.rule",
        inverse_name="dossier_id",
        string="Rules",
    )
