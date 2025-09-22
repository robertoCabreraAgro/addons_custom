from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    pos_load_all_partners_by_company = fields.Boolean(
        related="pos_config_id.load_all_partners_by_company",
        readonly=False,
    )

    sat_batch_size = fields.Integer(
        string="Tamaño de lote para validación SAT",
        default=50,
        config_parameter="l10n_mx_edi_marin.sat_batch_size",
    )

    sat_status_max_days = fields.Integer(
        string="Días hábiles para revisión SAT",
        default=60,
        config_parameter="l10n_mx_edi_marin.sat_status_max_days",
    )

    # Customer merge configuration
    customer_merge_active = fields.Boolean(
        string="Enable Automatic Customer Merge",
        default=False,
        help="Automatically merge inactive customers with the general public partner",
        config_parameter="customer_merge_active",
    )
    customer_merge_interval_number = fields.Integer(
        string="Evaluation Period",
        default=3,
        help="Number of time units for the evaluation period",
        config_parameter="customer_merge_interval_number",
    )
    customer_merge_interval_type = fields.Selection(
        selection=[("days", "Days"), ("weeks", "Weeks"), ("months", "Months")],
        string="Period Type",
        default="months",
        help="Time unit for the evaluation period",
        config_parameter="customer_merge_interval_type",
    )
    customer_merge_min_orders = fields.Integer(
        string="Minimum Orders Required",
        default=2,
        help="Minimum number of orders required to keep a customer active",
        config_parameter="customer_merge_min_orders",
    )
    customer_merge_general_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="General Public Partner",
        help="Partner to merge inactive customers with",
        config_parameter="customer_merge_general_partner_id",
    )
    customer_merge_required_fields = fields.Many2many(
        related="company_id.customer_merge_required_fields",
        comodel_name="ir.model.fields",
        string="Required Customer Fields",
        readonly=False,
        help="Fields that must be completed to keep a customer active",
    )

    # Restricted Contact Creation configuration
    restricted_contact_creation = fields.Boolean(
        string="Restricted Contact Creation",
        default=False,
        help="Restrict users in the selected group from creating or editing contacts unless all mandatory fields are completed.",
        config_parameter="sale.restricted_contact_creation",
    )
    restricted_contact_required_fields = fields.Many2many(
        related="company_id.restricted_contact_required_fields",
        comodel_name="ir.model.fields",
        string="Mandatory Contact Fields",
        readonly=False,
        help="Fields that must be completed when restricted contact creation is enabled",
    )

    # Restricted MRP planning configuration
    module_planning_mrp = fields.Boolean(
        string="Production itinerary",
    )
