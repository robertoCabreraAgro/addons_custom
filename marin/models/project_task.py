from odoo import fields, models, api


class Task(models.Model):
    """Inherit Task"""

    _inherit = "project.task"

    # Used in all project tasks
    lost_reason_id = fields.Many2one(
        "project.task.lost.reason",
        string="Lost Reason",
        index=True,
        ondelete="restrict",
        tracking=True,
    )

    # CRM
    company_currency = fields.Many2one(
        "res.currency",
        "Currency",
        compute="_compute_company_currency",
        compute_sudo=True,
    )
    expected_revenue = fields.Monetary(
        "Expected Revenue", currency_field="company_currency", tracking=True
    )
    referer_partner_id = fields.Many2one(
        "res.partner",
        "Referred By",
        check_company=True,
        index=True,
        tracking=10,
        help="A customer already existing in company",
    )
    # team_id = fields.Many2one(
    #    'crm.team',
    #    'Sales Team',
    #    check_company=True,
    #    index=True,
    #    tracking=True,
    #    compute='_compute_team_id', store=True, precompute=True
    #    ondelete="set null",
    #    readonly=False,
    # )

    # AG
    expected_area = fields.Float("Expected area", tracking=True)
    is_ag_initial = fields.Boolean("Initial AG task", default=False)
    season_id = fields.Many2one(
        "date.range",
        "AG season",
        help="Since every farmer can have several growing seasons the specific one can be selected.",
    )
    #Fields KPI
    kpi_optime_predev_min = fields.Float("Time before development", help="Estimated time the operation took before development")
    kpi_optime_postdev_min = fields.Float("Time after development", help="Estimated time the operation took after development")
    kpi_optime_frequency_type = fields.Selection(
    [        
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),        
        ("yearly", "Yearly"),        
    ],    
    string="Frequency Type",
    help="Frequency with which this operation occurs",
    )
    kpi_optime_frequency_interval = fields.Integer(string="Interval frequency", help="Number that indicates how many times the event occurs in the selected period")
    use_kpi_optime = fields.Boolean(
    related="project_id.use_kpi_optime",
    string="Use KPI time operative",
    store=False,
    )


    @api.depends("company_id")
    def _compute_company_currency(self):
        for task in self:
            if not task.company_id:
                task.company_currency = self.env.company.currency_id
            else:
                task.company_currency = task.company_id.currency_id

    # @api.depends('user_id')
    # def _compute_team_id(self):
    #    """ When changing the user, also set a team_id or restrict team id
    #    to the ones user_id is member of. """
    #    for task in self:
    #        if not task.user_id:
    #            continue
    #        user = task.user_id
    #        if task.team_id and user in (task.team_id.member_ids | task.team_id.user_id):
    #            continue
    #        team_domain = [('use_tasks', '=', True)] if task.type == 'task' else [('use_opportunities', '=', True)]
    #        team = self.env['crm.team']._get_default_team_id(user_id=user.id, domain=team_domain)
    #        if task.team_id != team:
    #            task.team_id = team.id

    def _prepare_task_quotation_context(self):
        """Prepares the context for a new quotation (sale.order) by sharing the values of common fields"""
        self.ensure_one()
        quotation_context = {
            # 'default_opportunity_id': self.id,
            "default_partner_id": self.partner_id.id,
            # 'default_campaign_id': self.campaign_id.id,
            # 'default_medium_id': self.medium_id.id,
            # 'default_source_id': self.source_id.id,
            "default_origin": self.name,
            "default_company_id": self.company_id.id or self.env.company.id,
            # 'default_tag_ids': [(6, 0, self.tag_ids.ids)]
        }
        # if self.team_id:
        #     quotation_context['default_team_id'] = self.team_id.id
        # if self.user_id:
        #     quotation_context['default_user_id'] = self.user_id.id
        return quotation_context

    def action_new_quotation(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "marin.action_quotation_new"
        )
        action["context"] = self._prepare_task_quotation_context()
        # action['context']['search_default_opportunity_id'] = self.id
        return action