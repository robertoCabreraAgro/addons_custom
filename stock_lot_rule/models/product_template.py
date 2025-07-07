from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    lot_rule_id = fields.Many2one(
        comodel_name="stock.lot.rule",
        string="Lot Rule",
        help="Rule to apply for lot nomenclature and automatic date calculations",
        index=True,
    )

    @api.depends("lot_rule_id")
    def _compute_lot_times(self):
        """Compute lot times based on lot rule configuration"""
        for record in self:
            if record.lot_rule_id:
                record.expiration_time = record.lot_rule_id.expiration_time
                record.use_time = record.lot_rule_id.use_time
                record.removal_time = record.lot_rule_id.removal_time
                record.alert_time = record.lot_rule_id.alert_time
            else:
                # Keep existing values if no rule is set
                pass

    # Override the computed fields to make them dependent on lot_rule_id
    expiration_time = fields.Integer(
        compute="_compute_lot_times",
        store=True,
        readonly=False,
        help="Number of days before a lot expires",
    )

    use_time = fields.Integer(
        compute="_compute_lot_times",
        store=True,
        readonly=False,
        help="Number of days before a lot should be used",
    )

    removal_time = fields.Integer(
        compute="_compute_lot_times",
        store=True,
        readonly=False,
        help="Number of days before a lot should be removed",
    )

    alert_time = fields.Integer(
        compute="_compute_lot_times",
        store=True,
        readonly=False,
        help="Number of days before a lot alert",
    )

    @api.onchange("lot_rule_id")
    def _onchange_lot_rule_id(self):
        """Update lot times when lot rule changes"""
        if self.lot_rule_id:
            self.expiration_time = self.lot_rule_id.expiration_time
            self.use_time = self.lot_rule_id.use_time
            self.removal_time = self.lot_rule_id.removal_time
            self.alert_time = self.lot_rule_id.alert_time
