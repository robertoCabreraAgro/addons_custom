from odoo import fields, models


CATEGORY_SELECTION = [
    ('required', 'Required'),
    ('optional', 'Optional'),
    ('no', 'None')
]


class AccountAsset(models.Model):
    _inherit = "account.asset"


    location = fields.Char(string="Location")

    has_property_identification = fields.Selection(
        CATEGORY_SELECTION,
        string="Has property ID",
        default="no",
    )
    has_sn = fields.Selection(
        CATEGORY_SELECTION,
        string="Has SN",
        default="no",
    )
    has_imei = fields.Selection(
        CATEGORY_SELECTION,
        string="Has IMEI",
        default="no",
    )
    has_electric_power_contract = fields.Selection(
        CATEGORY_SELECTION,
        string="Has electric power contract",
        default="no",
    )
    has_telephone_contract = fields.Selection(
        CATEGORY_SELECTION,
        string="Has telephone contract",
        default="no",
    )

    model_id_has_property_identification = fields.Selection(
        related="model_id.has_property_identification",
    )
    model_id_has_sn = fields.Selection(
        related="model_id.has_sn",
    )
    model_id_has_imei = fields.Selection(
        related="model_id.has_imei",
    )
    model_id_has_electric_power_contract = fields.Selection(
        related="model_id.has_electric_power_contract",
    )
    model_id_has_telephone_contract = fields.Selection(
        related="model_id.has_telephone_contract",
    )

    property_identification = fields.Char(string="Property identification")
    sn = fields.Char(string="SN")
    imei = fields.Char(string="IMEI")
    electric_power_contract = fields.Char(string="Electric power contract")
    telephone_contract = fields.Char(string="Telephone contract")
