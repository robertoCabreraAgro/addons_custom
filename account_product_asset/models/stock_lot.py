from odoo import Command, models, fields


class StockLot(models.Model):
    _inherit = 'stock.lot'

    account_move_ids = fields.One2many(
        comodel_name='account.move',
        compute='_compute_move_ids',
        string='Bills',
    )
    bill_count = fields.Integer(
        string="Bills Count",
        compute='_compute_move_ids',
    )

    def _compute_move_ids(self):
        """Compute accounting moves related to this asset."""
        if not self.env.user.has_group('account.group_account_readonly'):
            self.account_move_ids = False
            self.bill_count = 0
            return

        moves = self.env['account.move.line']._read_group(
            domain=[
                ('asset_id', 'in', self.ids),
                ('parent_state', '!=', 'cancel'),
                ('move_id.move_type', 'in', self.env['account.move'].get_purchase_types())
            ],
            groupby=['asset_id'],
            aggregates=['move_id:array_agg'],
        )
        asset_move_mapping = {asset.id: set(move_ids) for asset, move_ids in moves}
        for asset in self:
            asset.account_move_ids = [Command.set(asset_move_mapping.get(asset.id, []))]
            asset.bill_count = len(asset.account_move_ids)

    def action_view_bills(self):
        """Open the list of bills related to this asset."""
        self.ensure_one()
        form_view_ref = self.env.ref('account.view_move_form', False)
        list_view_ref = self.env.ref('account_product_asset.account_move_view_tree', False)
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_in_invoice_type')
        action.update({
            'views': [(list_view_ref.id, 'list'), (form_view_ref.id, 'form')],
            'domain': [('id', 'in', self.account_move_ids.ids)],
        })
        return action