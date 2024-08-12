from odoo import fields, models, api


class Task(models.Model):
    _inherit = "project.task"

    #Used in all project tasks
    lost_reason_id = fields.Many2one(
        'project.task.lost.reason', string='Lost Reason',
        index=True, ondelete='restrict', tracking=True)

    #CRM
    company_currency = fields.Many2one("res.currency", 'Currency', 
        compute="_compute_company_currency",
        compute_sudo=True
    )
    expected_revenue = fields.Monetary('Expected Revenue',
        currency_field='company_currency',
        tracking=True
    )
    referer_partner_id = fields.Many2one(
        'res.partner', 
        'Referred By', 
        check_company=True,
        index=True,
        tracking=10,
        help="A customer already existing in company"
    )
    #team_id = fields.Many2one(
    #    'crm.team',
    #    'Sales Team',
    #    check_company=True,
    #    index=True,
    #    tracking=True,
    #    compute='_compute_team_id', store=True, precompute=True
    #    ondelete="set null",
    #    readonly=False,
    #)

    # AG
    expected_area = fields.Float("Expected area",
        tracking=True
    )
    is_ag_initial = fields.Boolean("Initial AG task", default=False)
    season_id = fields.Many2one(
        "date.range",
        "AG season",
        help="Since every farmer can have several growing seasons the specific one can be selected.",
    )

    @api.depends('company_id')
    def _compute_company_currency(self):
        for task in self:
            if not task.company_id:
                task.company_currency = self.env.company.currency_id
            else:
                task.company_currency = task.company_id.currency_id

    #@api.depends('user_id')
    #def _compute_team_id(self):
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
