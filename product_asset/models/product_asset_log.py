from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class ProductAssetLog(models.Model):
    _name = "product.asset.log"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Logs for Assets"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
    )
    asset_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Asset",
        required=True,
    )
    operator_id = fields.Many2one(
        related="asset_id.operator_id",
        store=True,
        string="Operator",
    )
    asset_manager_id = fields.Many2one(
        related="asset_id.asset_manager_id",
        store=True,
        string="Asset Manager",
    )
    vendor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        ondelete="restrict",
    )
    product_category_id = fields.Many2one(
        related="product_id.categ_id",
        store=True,
        string="Product Category",
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("running", "Running"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="State",
        default="new",
        group_expand=True,
        tracking=True,
    )
    date = fields.Date(
        default=fields.Date.context_today,
        help="Date when the cost has been executed",
    )
    date_start = fields.Date(
        string="Start Date",
        default=fields.Date.context_today,
        tracking=True,
        help="Date when the coverage of the contract begins",
    )
    date_end = fields.Date(
        string="Expiration Date",
        default=lambda self: self.compute_next_year_date(
            fields.Date.context_today(self)
        ),
        tracking=True,
        help="Date when the coverage of the contract expirates "
        "(by default, one year after begin date)",
    )
    odometer = fields.Float(
        string="Odometer Value",
        # TODO improve logic for account.move.line to set odometer
        # or to inforce only on the view
        # required=True,
        help="Odometer measure of the Asset at the moment of this log",
    )
    amount = fields.Monetary(
        string="Cost",
        tracking=True,
    )
    qty_fuel = fields.Float(
        string="Fuel Quantity (Liters)",
        help="Quantity of fuel added to the vehicle",
    )
    efficiency = fields.Float(
        string="Efficiency (km/L)",
        aggregator="avg",
        help="Fuel efficiency in kilometers per liter",
    )
    inv_ref = fields.Char("Vendor Reference")
    notes = fields.Text()
    days_left = fields.Integer(
        string="Warning Date",
        compute="_compute_days_left",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def compute_next_year_date(self, strdate):
        start_date = fields.Date.from_string(strdate)
        return fields.Date.to_string(start_date + relativedelta(years=1))

    @api.depends("date_end")
    def _compute_days_left(self):
        today = fields.Date.from_string(fields.Date.today())
        for log in self:
            if log.date_end:
                renew_date = fields.Date.from_string(log.date_end)
                diff_time = (renew_date - today).days
                log.days_left = diff_time if diff_time > 0 else 0
            else:
                log.days_left = -1
