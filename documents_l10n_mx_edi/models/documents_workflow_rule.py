from odoo import _, fields, models


class WorkflowActionRuleEdi(models.Model):
    _inherit = "documents.workflow.rule"

    create_model = fields.Selection(selection_add=[("create.mx.edi.record", "CFDI")])

    def prepare_record_from_mx_edi_action(self):
        action = {
            'name': _('MX EDI to record'),
            'type': 'ir.actions.act_window',
            'res_model': 'documents.mx_edi_to_record_wizard',
            'view_mode': 'form',
            'target': 'new',
            'views': [(False, "form")],
            "context": {}
        }
        return action

    def create_record_from_mx_edi(self, documents):
        documents.check_document_already_linked()
        action = self.prepare_record_from_mx_edi_action()
        action.update({"context": {"default_document_ids": documents.ids}})
        return action

    def create_record(self, documents=None):
        self.ensure_one()
        if self.create_model == "create.mx.edi.record":
            return self.create_record_from_mx_edi(documents)
        return super().create_record(documents=documents)
