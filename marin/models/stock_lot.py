import datetime

from odoo import api, fields, models


class StockLot(models.Model):
    """Inherit StockLot"""

    _inherit = "stock.lot"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    original_expiration_date = fields.Date(
        string="Original Expiration Date",
        compute="_compute_original_expiration_date",
        store=True,
        help="Original expiration date before reconditioning",
    )

    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
    )

    fuel_card_id = fields.Many2one(
        domain=lambda self: [
            (
                "tag_ids",
                "in",
                self.env.ref("documents_product_asset.documents_tag_fuel_card").ids,
            ),
        ],
    )
    highway_pass_id = fields.Many2one(
        domain=lambda self: [
            (
                "tag_ids",
                "in",
                self.env.ref("documents_product_asset.documents_tag_highway_pass").ids,
            ),
        ],
    )

    l10n_mx_vehicle_code = fields.Char(
        string="Vehicle Code",
        tracking=True,
        help="In Mexico the tax authority assign a 7 character code to identify its characteristics.",
    )
    account_prefix = fields.Char(
        string="Account Prefix",
        tracking=True,
        help="This fields is required by Accounting to group according to its needs.",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("product_id")
    def _compute_expiration_date(self):
        self.expiration_date = False
        for lot in self:
            if lot.product_id.use_expiration_date and not lot.expiration_date:
                product_tmpl = lot.product_id.product_tmpl_id
                duration = (
                    product_tmpl.expiration_time
                    or product_tmpl.categ_id.expiration_time
                )
                lot.expiration_date = fields.Datetime.now() + datetime.timedelta(
                    days=duration
                )

    @api.depends("product_id", "expiration_date")
    def _compute_dates(self):
        for lot in self:
            if not lot.product_id.use_expiration_date:
                lot.use_date = False
                lot.removal_date = False
                lot.alert_date = False
            elif lot.expiration_date:
                # when create
                if (
                    lot.product_id != lot._origin.product_id
                    or (
                        not lot.use_date and not lot.removal_date and not lot.alert_date
                    )
                    or (lot.expiration_date and not lot._origin.expiration_date)
                ):
                    product_tmpl = lot.product_id.product_tmpl_id
                    categ = product_tmpl.categ_id
                    lot.use_date = lot.expiration_date - datetime.timedelta(
                        days=product_tmpl.use_time or categ.use_time
                    )
                    lot.removal_date = lot.expiration_date - datetime.timedelta(
                        days=product_tmpl.removal_time or categ.removal_time
                    )
                    lot.alert_date = lot.expiration_date - datetime.timedelta(
                        days=product_tmpl.alert_time or categ.alert_time
                    )
                # when change
                elif lot._origin.expiration_date:
                    time_delta = lot.expiration_date - lot._origin.expiration_date
                    lot.use_date = (
                        lot._origin.use_date and lot._origin.use_date + time_delta
                    )
                    lot.removal_date = (
                        lot._origin.removal_date
                        and lot._origin.removal_date + time_delta
                    )
                    lot.alert_date = (
                        lot._origin.alert_date and lot._origin.alert_date + time_delta
                    )

    @api.depends("expiration_date")
    def _compute_original_expiration_date(self):
        """Compute original expiration date.

        If original_expiration_date is False, assign the value of expiration_date.
        If original_expiration_date already has a value, keep it unchanged.
        """
        for lot in self:
            if not lot.original_expiration_date and lot.expiration_date:
                lot.original_expiration_date = lot.expiration_date
