from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    pos_load_all_partners_by_company = fields.Boolean(
        related="pos_config_id.load_all_partners_by_company", readonly=False
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
        config_parameter="customer_merge_active",
        default=False,
        help="Automatically merge inactive customers with the general public partner",
    )
    customer_merge_interval_number = fields.Integer(
        string="Evaluation Period",
        config_parameter="customer_merge_interval_number",
        default=3,
        help="Number of time units for the evaluation period",
    )
    customer_merge_interval_type = fields.Selection(
        [("days", "Days"), ("weeks", "Weeks"), ("months", "Months")],
        string="Period Type",
        config_parameter="customer_merge_interval_type",
        default="months",
        help="Time unit for the evaluation period",
    )
    customer_merge_min_orders = fields.Integer(
        string="Minimum Orders Required",
        config_parameter="customer_merge_min_orders",
        default=2,
        help="Minimum number of orders required to keep a customer active",
    )
    customer_merge_general_partner_id = fields.Many2one(
        "res.partner",
        string="General Public Partner",
        config_parameter="customer_merge_general_partner_id",
        help="Partner to merge inactive customers with",
    )
    customer_merge_required_fields = fields.Many2many(
        "ir.model.fields",
        related="company_id.customer_merge_required_fields",
        readonly=False,
        string="Required Customer Fields",
        help="Fields that must be completed to keep a customer active",
    )

    # Restricted Contact Creation configuration
    restricted_contact_creation = fields.Boolean(
        string="Restricted Contact Creation",
        config_parameter="sale.restricted_contact_creation",
        default=False,
        help="Restrict users in the selected group from creating or editing contacts unless all mandatory fields are completed.",
    )
    restricted_contact_required_fields = fields.Many2many(
        "ir.model.fields",
        related="company_id.restricted_contact_required_fields",
        readonly=False,
        string="Mandatory Contact Fields",
        help="Fields that must be completed when restricted contact creation is enabled",
    )
