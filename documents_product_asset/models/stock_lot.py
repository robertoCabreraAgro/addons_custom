from odoo import fields, models


class FleetVehicle(models.Model):
    _name = "stock.lot"
    _inherit = ["stock.lot", "documents.mixin"]

    documents_settings_fleet = fields.Boolean(
        related="company_id.documents_settings_fleet",
        string="Centralize Fleet Documents",
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
        return self.company_id.documents_folder_fleet_id

    def _get_document_owner(self):
        """User can see only their own documents in the fleet folder (see _get_document_vals_access_rights)."""
        return self.env.user

    def _get_document_tags(self):
        return self.company_id.documents_tags_fleet

    def _check_create_documents(self):
        return (
            self.company_id.documents_settings_fleet
            and super()._check_create_documents()
        )

    def action_view_attachments(self):
        self.ensure_one()
        if not self.company_id.documents_settings_fleet:
            return True
        fleet_folder = self._get_document_folder()
        fleet_tags = self._get_document_tags()
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
            "searchpanel_default_folder_id": fleet_folder.id,
            "searchpanel_default_tag_ids": fleet_tags.ids,
        }
        return action
