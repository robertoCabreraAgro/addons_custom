from odoo import fields, models, api
from odoo.exceptions import UserError


class Task(models.Model):
    """Inherit Task"""

    _inherit = "project.task"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    # Used in all project tasks
    lost_reason_id = fields.Many2one(
        comodel_name="project.task.lost.reason",
        string="Lost Reason",
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    # CRM
    company_currency = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        compute="_compute_company_currency",
        compute_sudo=True,
    )
    expected_revenue = fields.Monetary(
        string="Expected Revenue",
        currency_field="company_currency",
        tracking=True,
    )
    referer_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Referred By",
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
    expected_area = fields.Float(
        string="Expected area",
        tracking=True,
    )
    is_ag_initial = fields.Boolean(
        string="Initial AG task",
        default=False,
    )
    season_id = fields.Many2one(
        comodel_name="date.range",
        string="AG season",
        help="Since every farmer can have several growing seasons the specific one can be selected.",
    )
    sales_features = fields.Boolean(
        related="project_id.sales_features",
        string="Sales Features",
        store=False,
    )

    # Fields KPI
    kpi_optime_predev_min = fields.Float(
        string="Time before development",
        help="Estimated time the operation took before development",
    )
    kpi_optime_postdev_min = fields.Float(
        string="Time after development",
        help="Estimated time the operation took after development",
    )
    kpi_optime_frequency_type = fields.Selection(
        selection=[
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ],
        string="Frequency Type",
        help="Frequency with which this operation occurs",
    )
    kpi_optime_frequency_interval = fields.Integer(
        string="Interval frequency",
        help="Number that indicates how many times the event occurs in the selected period",
    )
    kpi_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="KPI Affected Employees",
        compute_sudo=True,
        help="Employees that are affected by this KPI. This is used to filter the employees that will be able to see the KPI in their dashboard.",
    )
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

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": self.sale_order_id.id,
        }

    def action_create_sale_order(self):
        if any(task.sale_order_id for task in self):
            concerned_task = self.filtered("sale_order_id")
            ref_str = "\n".join(task.name for task in concerned_task)
            raise UserError(
                self.env._(
                    "You cannot create a quotation for a task that is already linked to a sale order.\nConcerned task(s):\n%(ref_str)s",
                    ref_str=ref_str,
                ),
            )
        if any(not task.partner_id for task in self):
            concerned_task = self.filtered(lambda task: not task.partner_id)
            ref_str = "\n".join(task.name for task in concerned_task)
            raise UserError(
                self.env._(
                    "You need to define a customer on the task before creating a related quotation.\nConcerned task(s):\n%(ref_str)s",
                    ref_str=ref_str,
                ),
            )
        # Validate season requirement
        if any(not task.season_id for task in self):
            concerned_task = self.filtered(lambda task: not task.season_id)
            ref_str = "\n".join(task.name for task in concerned_task)
            raise UserError(
                self.env._(
                    "You need to define an agricultural season on the task before creating a related quotation.\nConcerned task(s):\n%(ref_str)s",
                    ref_str=ref_str,
                ),
            )

        sale_orders = self.env["sale.order"]
        for task in self:
            sale_order_values = {
                "company_id": task.company_id.id or self.env.company.id,
                "partner_id": task.partner_id.id,
                "season_id": task.season_id.id,
                "origin": task.name,
            }
            sale_order = self.env["sale.order"].create(sale_order_values)

            # Link the task to the created sale order
            task.write({"sale_order_id": sale_order.id})

            # Add chatter message to the sale order
            sale_order.message_post_with_source(
                "mail.message_origin_link",
                render_values={"self": sale_order, "origin": task},
                subtype_xmlid="mail.mt_note",
            )

            sale_orders |= sale_order

        if len(sale_orders) == 1:
            return self.action_view_sale_order()

        return {
            "type": "ir.actions.act_window",
            "name": _("Created Quotations"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", sale_orders.ids)],
        }
