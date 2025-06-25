from odoo import fields, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_mx_edi_require_uuid = fields.Boolean(
        string="Require a CFDI UUID",
        help="If checked, vendor bills created with this journal must have a CFDI UUID",
        default=False,
    )

    def create_document_from_attachment(self, attachment_ids):
        mx_edi_document = self.env["l10n_mx_edi.document"]
        ir_attachment = self.env["ir.attachment"]
        account_move = self.env["account.move"]
        check_duplicate = self.env.context.get("check_duplicate", True)
        duplicated_attachments = []
        for attachment_id in attachment_ids:
            name = ir_attachment.browse(attachment_id).name
            if name and name.lower().endswith(".xml") and check_duplicate:
                duplicity_result = mx_edi_document._get_duplicate_cfdi(name, account_move)
                if duplicity_result["duplicated"]:
                    duplicated_attachments.append(name)

        if duplicated_attachments:
            duplicated_list = "\n".join(duplicated_attachments)
            raise UserError(self.env._("Duplicated CFDI files detected:\n%s", duplicated_list))

        return super().create_document_from_attachment(attachment_ids)
