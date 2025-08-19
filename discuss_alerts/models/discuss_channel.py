import logging
import ast
from odoo import fields, models, api
from lxml import etree
from odoo.tools import html_sanitize

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    """Inherit DisucussChannel"""

    _inherit = "discuss.channel"

    alert_domain = fields.Text(
        string="Alert domain",
        default='[]'
    )
    alert_enabled = fields.Boolean(
        string="Canal alert",
        defaul=True
    )
    alert_active = fields.Boolean(
        string="Alert activa",
        defaul=True
    )
    alert_last_execution = fields.Datetime(
        string="Last execution",
        default=fields.Datetime.now
    )
    alert_model_id = fields.Selection(
        selection='_list_all_models',
        string='Alert model'
    )
    alert_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Alert template",
    )

    @api.model
    def _list_all_models(self):
        lang = self.env.lang or 'en_US'
        self._cr.execute(
            "SELECT model, COALESCE(name->>%s, name->>'en_US') FROM ir_model ORDER BY 2",
            [lang],
        )
        return self._cr.fetchall()

    @api.model
    def _process_alert_channels(self):
        """Cron job that processes channels with alerts enabled"""
        alert_channels = self.search([
            ('alert_enabled', '=', True),
            ('alert_active', '=', True)
        ])
        for channel in alert_channels:
            records = channel._evaluate_alert_domain()
            if records:
                for record in records:
                    channel.message_post(
                        body=channel._render_alert_message(record),
                        author_id=None,
                        message_type="comment"
                    )
                    channel.alert_last_execution = fields.Datetime.now()

    def _evaluate_alert_domain(self):
        """Evaluate configured domain with date filters"""
        if not self.alert_model_id:
            return self.env[self.alert_model_id].browse()

        # Convert the base domain
        base_domain = ast.literal_eval(self.alert_domain or '[]')

        # Create date domain
        date_domain = [('create_date', '<=', fields.Datetime.now())]
        if self.alert_last_execution:
            date_domain = date_domain + [('create_date', '>', self.alert_last_execution)]

        full_domain = base_domain + date_domain if self.alert_domain else date_domain

        return self.env[self.alert_model_id].search(full_domain)

    def _render_alert_message(self, record):
        """Renders the template content"""
        try:
            lang = self.env.user.lang or 'en_US'

            template_in_lang = self.alert_template_id.with_context(lang=lang)
            rendered_content = template_in_lang._render_field('body_html', record.ids)[record.id]
            return rendered_content
        except Exception as e:
            _logger.error("Error rendering alert template: %s", e)
            return self.alert_template_id.body_html or ""
