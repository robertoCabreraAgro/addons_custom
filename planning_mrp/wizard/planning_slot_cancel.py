from odoo import _, fields, models
from odoo.exceptions import ValidationError


class PlanningSlotCancel(models.TransientModel):
    _name = "planning.slot.cancel"
    _description = "Planning Slot Cancel"

    slot_ids = fields.Many2many(
        comodel_name="planning.slot",
        string="Planning slots to canceled",
        default=lambda self: self._get_active_slots(),
    )
    cancel_reason_id = fields.Many2one(
        comodel_name="planning.cancel.reason", string="Cancel reason", required=True, domain=[("active", "=", True)]
    )
    cancel_details = fields.Text(string="Additional Details")
    notify_employee = fields.Boolean(string="Notify Assigned Employee", default=True)

    def _get_active_slots(self):
        """Gets the active planning.slot from the context"""
        active_ids = self.env.context.get("active_ids", [])
        active_model = self.env.context.get("active_model", "")

        if active_model == "planning.slot" and active_ids:
            slots = self.env["planning.slot"].browse(active_ids)
            # Check for already cancelled slots
            if slots.filtered(lambda s: s.state == "cancelled"):
                raise ValidationError(_("You cannot cancel assignments that are already cancelled."))

            # Check for past slots
            now = fields.Datetime.now()
            past_slots = slots.filtered(lambda s: s.end_datetime and s.end_datetime < now)
            if past_slots:
                raise ValidationError(_("You cannot cancel shifts that have already ended."))

            return [(6, 0, active_ids)]

        return [(6, 0, [])]

    def _send_cancellation_notification(self, slot):
        """Send a cancellation notice to an employee."""
        employee_partner = slot.employee_id.related_partner_id
        if not employee_partner:
            return

        message_body = (
            f"Hello {slot.employee_id.name},\n"
            f"The assignment has been cancelled.\n"
            f"Here are the details:\n"
            f"Date init: {slot.start_datetime}\n"
            f"Date end: {slot.end_datetime}\n"
            f"Resource: {slot.resource_id.name if slot.resource_id else "N/A"}\n"
            f"Cancel reason: {slot.cancel_reason_id.name}\n"
            f"Cancel details: {slot.cancel_details if slot.cancel_details else "N/A"}\n"
            f"Cancel date: {slot.cancel_date}\n"
            f"Cancelled by: {self.env.user.name}"
        )

        slot.message_post(
            body=message_body,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
            partner_ids=[employee_partner.id],
        )

    def action_cancel(self):
        """
        Cancels the selected planning assignments.

        This function processes the planning slots the user has selected,
        updates their status to "cancelled", and associates them with a cancellation reason.
        If the "notify_employee" option is enabled, it sends a notification to each
        affected employee with the details of the cancellation.
        """
        active_ids = self.env.context.get("active_ids")
        if active_ids:
            planning_slot_ids = (
                self.env["planning.slot"].browse(active_ids).filtered(lambda pl: pl.state != "cancelled")
            )
            if not planning_slot_ids:
                return

            # Additional validation for past slots
            now = fields.Datetime.now()
            past_slots = planning_slot_ids.filtered(lambda s: s.end_datetime and s.end_datetime < now)
            if past_slots:
                raise ValidationError(_("You cannot cancel shifts that have already ended."))
            write_vals = {
                "cancel_reason_id": self.cancel_reason_id.id,
                "cancel_details": self.cancel_details,
                "cancel_date": fields.Datetime.now(),
                "cancelled_by": self.env.user.id,
                "state": "cancelled",
            }
            planning_slot_ids.write(write_vals)

            for slot in planning_slot_ids:
                if self.notify_employee and slot.employee_id:
                    self._send_cancellation_notification(slot)
        return
