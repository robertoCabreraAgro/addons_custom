from odoo import api, fields, models


class StockLot(models.Model):
    """Extend stock.lot with Documents integration and asset-type aware defaults."""

    _name = "stock.lot"
    _inherit = ["stock.lot", "documents.mixin"]

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    documents_settings_asset = fields.Boolean(
        compute="_compute_documents_settings_asset",
        string="Centralize Asset's Documents",
        help="When enabled for this asset type, opening attachments uses the configured folder and tags.",
    )
    fuel_card_id = fields.Many2one(
        comodel_name="documents.document",
        inverse="_inverse_fuel_card_id",
        store=True,
        readonly=False,
    )
    fuel_card_name = fields.Char(
        compute="_compute_fuel_card_name",
        store=True,
    )
    count_fuel_card = fields.Integer(
        "Fuel cards count",
        compute="_compute_count_fuel_card",
    )
    highway_pass_id = fields.Many2one(
        comodel_name="documents.document",
        inverse="_inverse_highway_pass_id",
        store=True,
        readonly=False,
    )
    highway_pass_name = fields.Char(
        compute="_compute_highway_pass_name",
        store=True,
    )
    count_highway_pass = fields.Integer(
        "Highway passes count",
        compute="_compute_count_highway_pass",
    )
    count_document = fields.Integer(
        string="Documents",
        compute="_compute_count_document",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_count_document(self):
        document_data = self.env["documents.document"]._read_group(
            [("res_id", "in", self.ids), ("res_model", "=", self._name)],
            groupby=["res_id"],
            aggregates=["__count"],
        )
        mapped_data = dict(document_data)
        for record in self:
            record.count_document = mapped_data.get(record.id, 0)

    def _compute_count_fuel_card(self):
        fuel_card_product = self.env.ref(
            "product_asset.product_product_fuel_credit", False
        )
        if not fuel_card_product:
            for asset in self:
                asset.count_fuel_card = 0
            return

        for asset in self:
            asset.count_fuel_card = len(
                asset.log_ids.filtered(lambda l: l.product_id == fuel_card_product)
            )

    def _compute_count_highway_pass(self):
        highway_pass_product = self.env.ref(
            "product_asset.product_product_highway_credit", False
        )
        if not highway_pass_product:
            for asset in self:
                asset.count_highway_pass = 0
            return

        for asset in self:
            asset.count_highway_pass = len(
                asset.log_ids.filtered(lambda l: l.product_id == highway_pass_product)
            )

    @api.depends("product_id")
    def _compute_documents_settings_asset(self):
        """Compute if documents are enabled for this asset type."""
        for record in self:
            asset_type = record.product_id.product_tmpl_id.asset_type or "product"

            settings_field_mapping = {
                "equipment": "documents_settings_equipment",
                "machinery": "documents_settings_machinery",
                "property": "documents_settings_property",
                "vehicle": "documents_settings_fleet",
                "product": "documents_product_settings",  # Default
            }

            settings_field = settings_field_mapping.get(
                asset_type, "documents_product_settings"
            )
            record.documents_settings_asset = getattr(
                record.company_id, settings_field, False
            )

    # ------------------------------------------------------------
    # INVERSE METHODS
    # ------------------------------------------------------------

    def _inverse_fuel_card_id(self):
        """
        Set the asset on the corresponding document
        """
        for asset in self:
            doc = asset.fuel_card_id
            if doc:
                doc.sudo().write(
                    {
                        "res_model": asset._name,
                        "res_id": asset.id,
                        "is_editable_attachment": True,
                    }
                )

    def _inverse_highway_pass_id(self):
        """
        Set the asset on the corresponding document
        """
        for asset in self:
            doc = asset.highway_pass_id
            if doc:
                doc.sudo().write(
                    {
                        "res_model": asset._name,
                        "res_id": asset.id,
                        "is_editable_attachment": True,
                    }
                )

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _get_document_folder(self):
        """Return the company-configured documents.folder for this lot's asset_type, or an empty recordset."""
        asset_type = self.product_id.product_tmpl_id.asset_type or "product"
        folder_field_mapping = {
            "equipment": "documents_folder_equipment_id",
            "machinery": "documents_folder_machinery_id",
            "property": "documents_folder_property_id",
            "vehicle": "documents_folder_fleet_id",
            "product": "product_folder_id",  # Default
        }
        folder_field = folder_field_mapping.get(asset_type, "product_folder_id")
        return getattr(self.company_id, folder_field, self.env["documents.document"])

    def _get_document_owner(self):
        """User can see only their own documents in the fleet folder (see _get_document_vals_access_rights)."""
        return self.env.user

    def _get_document_tags(self):
        """Return the company-configured documents.tag recordset for this lot's asset_type (may be empty)."""
        asset_type = self.product_id.product_tmpl_id.asset_type or "product"
        tags_field_mapping = {
            "equipment": "documents_tags_equipment",
            "machinery": "documents_tags_machinery",
            "property": "documents_tags_property",
            "vehicle": "documents_tags_fleet",
            "product": "product_tag_ids",  # Default
        }
        tags_field = tags_field_mapping.get(asset_type, "product_tag_ids")
        return getattr(self.company_id, tags_field, self.env["documents.tag"])

    # ------------------------------------------------------------
    # VALIDATORS
    # ------------------------------------------------------------

    def _check_create_documents(self):
        """Return True if company settings allow document creation for this asset_type and super allows it."""
        asset_type = self.product_id.product_tmpl_id.asset_type or "product"
        settings_field_mapping = {
            "equipment": "documents_settings_equipment",
            "machinery": "documents_settings_machinery",
            "property": "documents_settings_property",
            "vehicle": "documents_settings_fleet",
            "product": "documents_product_settings",  # Default
        }
        settings_field = settings_field_mapping.get(
            asset_type, "documents_product_settings"
        )
        return (
            getattr(self.company_id, settings_field, False)
            and super()._check_create_documents()
        )
