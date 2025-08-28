from odoo import api, fields, models
from odoo.osv import expression


class ResCompany(models.Model):
    _inherit = "res.company"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    documents_settings_equipment = fields.Boolean(default=True)
    documents_folder_equipment_id = fields.Many2one(
        "documents.document",
        string="Equipment Folder",
        compute="_compute_documents_folder_equipment_id",
        store=True,
        readonly=False,
        domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False), '|', ('company_id', '=', False), ('company_id', '=', id)]",
    )
    documents_tags_equipment = fields.Many2many(
        "documents.tag",
        "documents_tags_equipment_table",
    )
    documents_settings_fleet = fields.Boolean(default=True)
    documents_folder_fleet_id = fields.Many2one(
        "documents.document",
        string="Fleet Folder",
        compute="_compute_documents_folder_fleet_id",
        store=True,
        readonly=False,
        domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False), '|', ('company_id', '=', False), ('company_id', '=', id)]",
    )
    documents_tags_fleet = fields.Many2many(
        "documents.tag",
        "documents_tags_fleet_table",
    )
    documents_settings_machinery = fields.Boolean(default=True)
    documents_folder_machinery_id = fields.Many2one(
        "documents.document",
        string="Machinery Folder",
        compute="_compute_documents_folder_machinery_id",
        store=True,
        readonly=False,
        domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False), '|', ('company_id', '=', False), ('company_id', '=', id)]",
    )
    documents_tags_machinery = fields.Many2many(
        "documents.tag",
        "documents_tags_machinery_table",
    )
    documents_settings_property = fields.Boolean(default=True)
    documents_folder_property_id = fields.Many2one(
        "documents.document",
        string="Property Folder",
        compute="_compute_documents_folder_property_id",
        store=True,
        readonly=False,
        domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False), '|', ('company_id', '=', False), ('company_id', '=', id)]",
    )
    documents_tags_property = fields.Many2many(
        "documents.tag",
        "documents_tags_property_table",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("documents_settings_equipment")
    def _compute_documents_folder_equipment_id(self):
        folder_id = self.env.ref(
            "documents_product_asset.document_folder_equipment",
            raise_if_not_found=False,
        )
        self._reset_default_documents_folder_id(
            "documents_settings_equipment", "documents_folder_equipment_id", folder_id
        )

    @api.depends("documents_settings_fleet")
    def _compute_documents_folder_fleet_id(self):
        folder_id = self.env.ref(
            "documents_product_asset.document_folder_fleet",
            raise_if_not_found=False,
        )
        self._reset_default_documents_folder_id(
            "documents_settings_fleet", "documents_folder_fleet_id", folder_id
        )

    @api.depends("documents_settings_machinery")
    def _compute_documents_folder_machinery_id(self):
        folder_id = self.env.ref(
            "documents_product_asset.document_folder_macchinery",
            raise_if_not_found=False,
        )
        self._reset_default_documents_folder_id(
            "documents_settings_machinery", "documents_folder_machinery_id", folder_id
        )

    @api.depends("documents_settings_property")
    def _compute_documents_folder_property_id(self):
        folder_id = self.env.ref(
            "documents_product_asset.document_folder_property",
            raise_if_not_found=False,
        )
        self._reset_default_documents_folder_id(
            "documents_settings_property", "documents_folder_property_id", folder_id
        )

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _get_used_folder_ids_domain(self, folder_ids):
        return expression.OR(
            [
                super()._get_used_folder_ids_domain(folder_ids),
                [
                    ("documents_folder_fleet_id", "in", folder_ids),
                    ("documents_settings_fleet", "=", True),
                ],
            ]
        )
