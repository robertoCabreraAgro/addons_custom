from odoo import fields, models


class StockLot(models.Model):
    _inherit = ["stock.lot", "documents.mixin"]

    documents_settings_asset = fields.Boolean(
        compute="_compute_documents_settings_asset",
        string="Centralize Asset Documents",
        help="When enabled for this asset type, opening attachments uses the configured folder and tags.",
    )
    count_document = fields.Integer(
        string="Documents",
        compute="_compute_count_document",
    )

    def _compute_count_document(self):
        document_data = self.env["documents.document"]._read_group(
            [("res_id", "in", self.ids), ("res_model", "=", self._name)],
            groupby=["res_id"],
            aggregates=["__count"],
        )
        mapped_data = dict(document_data)
        for record in self:
            record.count_document = mapped_data.get(record.id, 0)

    def _get_document_folder(self):
        asset_type = self.product_id.product_tmpl_id.asset_type or 'product'

        folder_field_mapping = {
            'equipment': 'documents_folder_equipment_id',
            'machinery': 'documents_folder_machinery_id',
            'property': 'documents_folder_property_id',
            'vehicle': 'documents_folder_fleet_id',
            'product': 'documents_folder_equipment_id',  # Default
        }

        folder_field = folder_field_mapping.get(asset_type, 'documents_folder_equipment_id')
        return getattr(self.company_id, folder_field, self.env['documents.document'])

    def _get_document_owner(self):
        """User can see only their own documents in the fleet folder (see _get_document_vals_access_rights)."""
        return self.env.user

    def _get_document_tags(self):
        asset_type = self.product_id.product_tmpl_id.asset_type or 'product'

        tags_field_mapping = {
            'equipment': 'documents_tags_equipment',
            'machinery': 'documents_tags_machinery',
            'property': 'documents_tags_property',
            'vehicle': 'documents_tags_fleet',
            'product': 'documents_tags_equipment',  # Default
        }

        tags_field = tags_field_mapping.get(asset_type, 'documents_tags_equipment')
        return getattr(self.company_id, tags_field, self.env['documents.tag'])

    def _check_create_documents(self):
        asset_type = self.product_id.product_tmpl_id.asset_type or 'product'

        settings_field_mapping = {
            'equipment': 'documents_settings_equipment',
            'machinery': 'documents_settings_machinery',
            'property': 'documents_settings_property',
            'vehicle': 'documents_settings_fleet',
            'product': 'documents_settings_equipment',  # Default
        }

        settings_field = settings_field_mapping.get(asset_type, 'documents_settings_equipment')
        return (
            getattr(self.company_id, settings_field, False)
            and super()._check_create_documents()
        )

    def _compute_documents_settings_asset(self):
        """Compute if documents are enabled for this asset type."""
        for record in self:
            asset_type = record.product_id.product_tmpl_id.asset_type or 'equipment'

            settings_field_mapping = {
                'equipment': 'documents_settings_equipment',
                'machinery': 'documents_settings_machinery',
                'property': 'documents_settings_property',
                'vehicle': 'documents_settings_fleet',
                'product': 'documents_settings_equipment',  # Default
            }

            settings_field = settings_field_mapping.get(asset_type, 'documents_settings_equipment')
            record.documents_settings_asset = getattr(record.company_id, settings_field, False)

    def action_view_attachments(self):
        self.ensure_one()
        if not self.documents_settings_asset:
            return True
        asset_folder = self._get_document_folder()
        asset_tags = self._get_document_tags()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "documents.document_action_preference"
        )
        action["domain"] = [
            "|",
            ("type", "=", "folder"),
            "&",
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
        ]
        action["context"] = {
            "default_res_id": self.id,
            "default_res_model": self._name,
            "searchpanel_default_folder_id": asset_folder.id,
            "searchpanel_default_tag_ids": asset_tags.ids,
        }
        return action
