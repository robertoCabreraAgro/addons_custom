from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    asset_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Asset',
        index='btree_not_null',
        help='Asset associated with this accounting line',
    )
    need_asset = fields.Boolean(
        compute='_compute_need_asset',
        help='Used to decide whether the asset_id field is editable',
    )
    asset_log_ids = fields.One2many(
        comodel_name='product.asset.log',
        inverse_name='account_move_line_id',
        export_string_translation=False,
    )

    def write(self, vals):
        """Update asset logs when asset_id changes."""
        if 'asset_id' in vals and not vals['asset_id']:
            self.sudo().asset_log_ids.with_context(ignore_linked_bill_constraint=True).unlink()
        return super().write(vals)

    def unlink(self):
        """Clean up asset logs when deleting the line."""
        self.sudo().asset_log_ids.with_context(ignore_linked_bill_constraint=True).unlink()
        return super().unlink()

    def _compute_need_asset(self):
        """Determine if asset field should be shown/required."""
        self.need_asset = False

    def _prepare_asset_log(self):
        """Prepare data for creating asset log entry."""
        return {
            'asset_id': self.asset_id.id,
            'vendor_id': self.partner_id.id,
            'product_id': self.product_id.id,
            'account_move_line_id': self.id,
        }