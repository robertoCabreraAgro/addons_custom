import datetime

from odoo import api, fields, models
from odoo.tools import float_is_zero


class StockLot(models.Model):
    _inherit = "stock.lot"

    active = fields.Boolean(default=True)

    # OVERRIDE
    @api.model
    def get_available_lots_for_pos(self, product_id, company_id, config_id):
        """Override the parent function  from module 'pos_lot_selection'
        so the lots appear ordered by their removal strategy."""
        config = self.env["pos.config"].browse(config_id)
        location = config.picking_type_id.default_location_src_id
        lots = self.sudo().search(
            [
                "&",
                ["product_id", "=", product_id],
                "|",
                ["company_id", "=", company_id],
                ["company_id", "=", False],
            ]
        )

        lots = lots.filtered(lambda ln: not float_is_zero(ln.product_qty, precision_digits=ln.product_uom_id.rounding))

        quant = self.env["stock.quant"]
        product = self.env["product.product"].browse(product_id)

        removal_strategy = quant._get_removal_strategy(product, product.location_id)
        domain = quant._get_gather_domain(product, product.location_id)
        domain, removal_strategy_order = quant._get_removal_strategy_domain_order(domain, removal_strategy, 0)

        quants = lots.quant_ids
        ordered_quants = quant.search(
            [("id", "in", quants.ids), ("location_id", "child_of", location.id)], order=removal_strategy_order
        )
        ordered_lots = ordered_quants.lot_id

        res = []
        for lot in ordered_lots:
            available_qty = sum(
                lot.quant_ids.filtered(
                    lambda quant: quant.location_id.usage == "internal"
                    or (quant.location_id.usage == "transit" and quant.location_id.company_id)
                ).mapped("available_quantity")
            )
            res.append(
                {
                    "id": lot.id,
                    "name": lot.name,
                    "on_hand_qty": lot.product_qty,
                    "available_qty": available_qty,
                    "expiration_date": lot.expiration_date,
                }
            )
        return res

    @api.depends("product_id")
    def _compute_expiration_date(self):
        self.expiration_date = False
        for lot in self:
            if lot.product_id.use_expiration_date and not lot.expiration_date:
                product_tmpl = lot.product_id.product_tmpl_id
                duration = product_tmpl.expiration_time or product_tmpl.categ_id.expiration_time
                lot.expiration_date = datetime.datetime.now() + datetime.timedelta(days=duration)

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
                    or (not lot.use_date and not lot.removal_date and not lot.alert_date)
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
                    lot.use_date = lot._origin.use_date and lot._origin.use_date + time_delta
                    lot.removal_date = lot._origin.removal_date and lot._origin.removal_date + time_delta
                    lot.alert_date = lot._origin.alert_date and lot._origin.alert_date + time_delta
