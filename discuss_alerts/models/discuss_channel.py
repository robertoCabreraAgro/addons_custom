import ast
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    alert_domain = fields.Text(string="Alert domain", default="[]")
    is_alert_channel = fields.Boolean(
        string="Alert Channel",
        default=False,
        help="Enable this to dedicate this channel exclusively for system alerts",
    )
    alert_last_execution = fields.Datetime(string="Last execution", default=fields.Datetime.now)
    alert_model_id = fields.Selection(selection="_list_all_models", string="Alert model")
    alert_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Alert template",
    )
    alert_template_body = fields.Html(
        string="Template Body",
        compute="_compute_alert_template_body",
        inverse="_inverse_alert_template_body",
        store=False,
    )
    alert_frequency = fields.Selection(
        selection=[
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ],
        string="Frequency",
        default="daily",
        help="Minimum time interval between alert executions",
    )

    @api.depends("alert_template_id")
    def _compute_alert_template_body(self):
        """Compute template body from selected template"""
        for channel in self:
            alert_template_body = False
            if channel.alert_template_id:
                alert_template_body = channel.alert_template_id.body_html

            channel.alert_template_body = alert_template_body

    @api.onchange("alert_model_id")
    def _onchange_alert_model_id(self):
        """Clear template when model changes"""
        if self.alert_model_id:
            self.alert_template_id = False
            self.alert_domain = "[]"

    def _inverse_alert_template_body(self):
        """Update template body when edited"""
        for channel in self:
            if channel.alert_template_id:
                channel.alert_template_id.body_html = channel.alert_template_body

    @api.model
    def _list_all_models(self):
        lang = self.env.lang or "en_US"
        self._cr.execute(
            "SELECT model, COALESCE(name->>%s, name->>'en_US') FROM ir_model ORDER BY 2",
            [lang],
        )
        return self._cr.fetchall()

    def _should_send_alert(self):
        """Check if enough time has passed based on alert frequency"""
        if not self.alert_last_execution or not self.alert_frequency:
            return True

        now = fields.Datetime.now()
        last_execution = self.alert_last_execution

        frequency_deltas = {
            "hourly": timedelta(hours=1),
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),  # Approximate month
        }

        required_interval = frequency_deltas.get(self.alert_frequency, timedelta(days=1))
        time_since_last = now - last_execution

        return time_since_last >= required_interval

    @api.model
    def _process_alert_channels(self):
        """Cron job that processes channels with alerts enabled"""
        alert_channels = self.search([("is_alert_channel", "=", True), ("active", "=", True)])
        for channel in alert_channels:
            if not channel._should_send_alert():
                continue

            records = channel._evaluate_alert_domain()
            if records:
                for record in records:
                    channel.message_post(
                        body=channel._render_alert_message(record), author_id=None, message_type="comment"
                    )
                channel.alert_last_execution = fields.Datetime.now()

    def _evaluate_alert_domain(self):
        """Evaluate configured domain with date filters"""
        if not self.alert_model_id:
            return self.env[self.alert_model_id].browse()

        # Convert the base domain
        base_domain = ast.literal_eval(self.alert_domain or "[]")

        # Only add date filters if we have a base domain
        # The frequency check is now handled at the channel level
        if self.alert_domain:
            return self.env[self.alert_model_id].search(base_domain)

        # If no domain is specified, return empty recordset
        return self.env[self.alert_model_id].browse()

    def _render_alert_message(self, record):
        """Renders the template content"""
        try:
            lang = self.env.user.lang or "en_US"

            template_in_lang = self.alert_template_id.with_context(lang=lang)
            rendered_content = template_in_lang._render_field("body_html", record.ids)[record.id]
            return rendered_content
        except Exception as e:
            _logger.error("Error rendering alert template: %s", e)
            return self.alert_template_id.body_html or ""
