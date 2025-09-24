from odoo import _, api, models
from odoo.exceptions import UserError


class IrAttachment(models.Model):
    """
    Attachment Extension for Approval Requests.

    This model extends ir.attachment to add business rules specific to
    approval request attachments. It ensures data integrity by preventing
    the deletion of attachments linked to finalized approval requests.

    The extension protects attachments that serve as audit trail evidence
    for completed approval processes, maintaining compliance and traceability.
    """

    _inherit = "ir.attachment"

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    @api.ondelete(at_uninstall=False)
    def _unlink_approved_approval_request(self):
        """
        Prevent deletion of attachments linked to finalized approval requests.

        This method enforces a business rule that attachments cannot be deleted
        if they are linked to approval requests in final states (approved, refused,
        or canceled). This ensures audit trail integrity and prevents tampering
        with historical approval documentation.

        The check only applies to attachments directly linked to approval.request
        records (not field-specific attachments like images).

        :raises UserError: If attempting to delete attachment linked to a
                          finalized approval request
        :return: None
        """
        approval_request_ids = [
            attachment.res_id
            for attachment in self
            if attachment.res_model == "approval.request" and not attachment.res_field
        ]
        if not approval_request_ids:
            return

        approval_requests = self.env["approval.request"].browse(approval_request_ids)
        for approval_request in approval_requests:
            if approval_request.state in ["approved", "refused", "cancel"]:
                raise UserError(
                    _(
                        """You cannot unlink an attachment which is linked to a 
                        validated, refused or cancelled approval request.""",
                    ),
                )
