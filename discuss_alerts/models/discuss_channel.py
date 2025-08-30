import ast
import json
import logging
from datetime import timedelta
from urllib.parse import urlencode, quote
from odoo import api, fields, models
from odoo.exceptions import UserError
from markupsafe import Markup

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

    @api.onchange("alert_model_id")
    def _onchange_alert_model_id(self):
        """Clear template when model changes"""
        if self.alert_model_id:
            self.alert_domain = "[]"

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
                action_url = channel.generate_action_url(records)
                message_body = channel._build_alert_message(records, action_url)

                channel.message_post(
                    body=Markup(message_body),
                    subject="Critical Tracking Points Summary",
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
                channel.alert_last_execution = fields.Datetime.now()

    def _evaluate_alert_domain(self):
        """Evaluate configured domain with date filters"""
        if not self.alert_model_id:
            return self.env["ir.model"].browse()

        # Convert the base domain
        base_domain = ast.literal_eval(self.alert_domain or "[]")

        # Only add date filters if we have a base domain
        # The frequency check is now handled at the channel level
        if self.alert_domain:
            return self.env[self.alert_model_id].search(base_domain)

        # If no domain is specified, return empty recordset
        return self.env["ir.model"].browse()

    def _build_alert_message(self, records, action_url):
        message = f"""
            <p><strong>{len(records)} critical tracking points</strong> have been identified.</p>
            <p>You can review them by clicking the following button:</p>
            <br/>
            <a href="{action_url}"
            style="background-color: #875A7B; color: #FFFFFF; padding: 10px 20px;
                    text-decoration: none; border-radius: 5px; font-weight: bold;"
            data-oe-model="{records._name}"
            data-oe-ids="[{','.join(map(str, records.ids))}]">
                View Critical Points
            </a>
            <br/>
        """
        return message

    def generate_action_url(self, records):
        """
        Generate a direct URL to a filtered list view using Odoo's modern URL structure.

        Args:
        records: Recordset for which the URL will be generated.

        Returns:
        str: Complete URL to the Odoo action with domain filter.

        Raises:
        UserError: If no suitable window action is found for the model.
        """
        # If recordset is empty, nothing to show
        if not records:
            return ""

        # 1. Get system base URL
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        if not base_url:
            raise UserError("System base URL (web.base.url) is not configured.")

        model_name = records._name

        # 2. Search for a window action for the model
        action = self.env["ir.actions.act_window"].search([
            ("res_model", "=", model_name),
            ("view_mode", "=like", "%list%"),
        ], limit=1)

        if not action:
            action = self.env["ir.actions.act_window"].search([
                ("res_model", "=", model_name),
            ], limit=1)

        # 3. If no action exists, create URL without action
        if not action:
            # Alternative: direct model/view approach
            domain = [('id', 'in', records.ids)]
            params = {
                'model': model_name,
                'view_type': 'list',
                'domain': json.dumps(domain),
            }
            query_string = urlencode(params)
            return f"{base_url}/web#{query_string}"

        # 4. Build the domain filter
        domain = [('id', 'in', records.ids)]

        # 5. Build action context - this is the correct format for Odoo 16+
        action_context = {
            'active_model': model_name,
            'active_ids': records.ids,
            'active_id': records.ids[0] if records.ids else False,
            'search_default_filter': True,
        }

        # 6. The correct URL format for Odoo with action and domain
        # Domain needs to be passed as a state parameter
        state = {
            'domain': domain,
            'context': action_context,
        }

        # Create the URL with proper encoding
        url = f"{base_url}/web#action={action.id}&model={model_name}&view_type=list"

        # Add the domain as a cids parameter (client IDs)
        if records.ids:
            url += f"&cids={','.join(map(str, records.ids))}"
            # Alternative: encode the full state
            url += f"&active_domain={quote(json.dumps(domain))}"

        return url
