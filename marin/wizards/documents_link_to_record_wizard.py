from odoo import models


class LinkToRecordWizard(models.TransientModel):
    _inherit = "documents.link_to_record_wizard"

    def link_to(self):
        res = super().link_to()
        fc_tag = self.env.ref("marin.documents_fleet_fuel_card", False)
        hp_tag = self.env.ref("marin.documents_fleet_highway_pass", False)
        if self.resource_ref._name == "fleet.vehicle":
            for doc in self.document_ids:
                if fc_tag and fc_tag in self.document_ids.tag_ids:
                    self.resource_ref.fuel_card_id = doc
                elif hp_tag and hp_tag in self.document_ids.tag_ids:
                    self.resource_ref.fuel_card_id = doc
        return res
