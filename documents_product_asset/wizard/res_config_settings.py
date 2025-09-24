from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    documents_settings_equipment = fields.Boolean(
        related="company_id.documents_settings_equipment",
        string="Equipment",
        readonly=False,
    )
    documents_folder_equipment_id = fields.Many2one(
        related="company_id.documents_folder_equipment_id",
        comodel_name="documents.document",
        string="Equipment Workspace",
        readonly=False,
        domain=[("type", "=", "folder"), ("shortcut_document_id", "=", False)],
    )
    documents_tags_equipment = fields.Many2many(
        related="company_id.documents_tags_equipment",
        comodel_name="documents.tag",
        string="Equipment Default Tags",
        readonly=False,
    )
    documents_settings_fleet = fields.Boolean(
        related="company_id.documents_settings_fleet",
        string="Fleet",
        readonly=False,
    )
    documents_folder_fleet_id = fields.Many2one(
        related="company_id.documents_folder_fleet_id",
        comodel_name="documents.document",
        string="Fleet Workspace",
        readonly=False,
        domain=[("type", "=", "folder"), ("shortcut_document_id", "=", False)],
    )
    documents_tags_fleet = fields.Many2many(
        related="company_id.documents_tags_fleet",
        comodel_name="documents.tag",
        string="Fleet Default Tags",
        readonly=False,
    )
    documents_settings_machinery = fields.Boolean(
        related="company_id.documents_settings_machinery",
        string="Machinery",
        readonly=False,
    )
    documents_folder_machinery_id = fields.Many2one(
        related="company_id.documents_folder_machinery_id",
        comodel_name="documents.document",
        string="Machinery Workspace",
        readonly=False,
        domain=[("type", "=", "folder"), ("shortcut_document_id", "=", False)],
    )
    documents_tags_machinery = fields.Many2many(
        related="company_id.documents_tags_machinery",
        comodel_name="documents.tag",
        string="Machinery Default Tags",
        readonly=False,
    )
    documents_settings_property = fields.Boolean(
        related="company_id.documents_settings_property",
        string="Property",
        readonly=False,
    )
    documents_folder_property_id = fields.Many2one(
        related="company_id.documents_folder_property_id",
        comodel_name="documents.document",
        string="Property Workspace",
        readonly=False,
        domain=[("type", "=", "folder"), ("shortcut_document_id", "=", False)],
    )
    documents_tags_property = fields.Many2many(
        related="company_id.documents_tags_property",
        comodel_name="documents.tag",
        string="Property Default Tags",
        readonly=False,
    )
