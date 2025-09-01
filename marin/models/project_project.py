from odoo import fields, models, api


class Task(models.Model):
    """Inherit Project"""

    _inherit = "project.project"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    use_kpi_optime = fields.Boolean(
        string="Use KPI time operative",
        help="Activate the operational time fields in the tasks of this project",
    )
    sales_features = fields.Boolean(
        string="Allow Quotations",
        help="Allow creating quotations from tasks in this project",
        default=False,
    )
