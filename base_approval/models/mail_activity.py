from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailActivity(models.Model):
    """
    Mail Activity Extension for Approvals.

    This model extends the mail.activity to add approval-specific functionality.
    It enriches activity data with approver information when activities are
    related to approval requests.

    The extension allows the Discuss app and activity widgets to display
    approval-specific context, such as which approver is assigned to an
    activity and their current approval state.
    """

    _inherit = "mail.activity"

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _to_store_defaults(self):
        """
        Define additional fields to include in the store representation.

        Extends the default fields list to include 'approver' field,
        which will be processed by the _to_store method for approval activities.

        :return: List of field names to include in store representation
        :rtype: list
        """
        return super()._to_store_defaults() + ["approver"]

    def _to_store(self, store: Store, fields):
        """
        Convert activity data to store format with approval context.

        This method enriches mail activities related to approval requests
        with additional context about the approver and their state.
        This information is used by the Discuss app and activity widgets
        to provide approval-specific UI elements.

        The method:
        1. Processes standard fields through parent implementation
        2. Identifies activities related to approval requests
        3. Adds approver ID and state to the activity data

        :param store: Store object to add activity data to
        :type store: Store
        :param fields: List of fields to include in the store
        :type fields: list
        :return: None
        """
        super()._to_store(store, [field for field in fields if field != "approver"])
        if "approver" not in fields:
            return

        activity_type_approval_id = self.env.ref(
            "base_approval.mail_activity_data_approval"
        )
        for activity in self.filtered(
            lambda activity: activity["res_model"] == "approval.request"
            and activity.activity_type_id == activity_type_approval_id
        ):
            request = self.env["approval.request"].browse(activity["res_id"])
            approver = request.approver_ids.filtered(
                lambda approver: activity.user_id == approver.user_id
            )
            store.add(
                activity,
                {"approver_id": approver.id, "approver_state": approver.state},
            )
