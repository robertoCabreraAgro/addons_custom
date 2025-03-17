from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def _to_store_defaults(self):
        return super()._to_store_defaults() + ["approver"]

    def _to_store(self, store: Store, fields):
        super()._to_store(store, [field for field in fields if field != "approver"])
        if "approver" not in fields:
            return

        activity_type_approval_id = self.env.ref(
            "approvals.mail_activity_data_approval"
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
                {"approver_id": approver.id, "approver_status": approver.status},
            )
