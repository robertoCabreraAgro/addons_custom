from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleTarget(models.Model):
    """Sales target management for customer objectives by period."""

    _name = "sale.target"
    _description = "Sales Target"
    _order = "date_from desc, partner_id"
    _rec_name = "name"

    name = fields.Char(
        string="Target Name",
        compute="_compute_name",
        store=True,
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
    )
    template_id = fields.Many2one(
        "sale.order.template",
        string="Quotation Template",
        required=True,
    )
    season_id = fields.Many2one(
        "date.range",
        string="Agricultural Season",
        related="template_id.season_id",
        store=True,
        readonly=True,
    )
    profile_id = fields.Many2one(
        "res.partner.profile",
        string="Customer Profile",
        related="partner_id.profile_id",
        store=True,
        readonly=True,
    )
    hectares = fields.Float(
        string="Hectares",
        related="partner_id.hectares",
        readonly=True,
    )
    factor = fields.Float(
        string="Profile Factor",
        related="profile_id.factor",
        readonly=True,
    )
    target_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
    )
    line_ids = fields.One2many(
        "sale.target.line",
        "target_id",
        string="Target Lines",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )

    @api.depends("partner_id", "template_id", "date_from", "date_to")
    def _compute_name(self):
        for target in self:
            if all([target.partner_id, target.template_id, 
                   target.date_from, target.date_to]):
                target.name = (f"{target.partner_id.name} - "
                              f"{target.template_id.name} "
                              f"({target.date_from} - {target.date_to})")
            else:
                target.name = "New Sales Target"

    @api.depends("line_ids.target_amount")
    def _compute_amounts(self):
        for target in self:
            target.target_amount = sum(target.line_ids.mapped("target_amount"))

    @api.constrains("date_from", "date_to", "partner_id")
    def _check_overlapping_periods(self):
        for target in self:
            if not all([target.date_from, target.date_to, target.partner_id]):
                continue
                
            if target.date_from > target.date_to:
                raise ValidationError("End date must be after start date.")

            overlapping = self.search([
                ("id", "!=", target.id),
                ("partner_id", "=", target.partner_id.id),
                "|",
                "&", ("date_from", "<=", target.date_from),
                     ("date_to", ">=", target.date_from),
                "&", ("date_from", "<=", target.date_to),
                     ("date_to", ">=", target.date_to),
            ])

            if overlapping:
                raise ValidationError(
                    f"Overlapping target found for {target.partner_id.name} "
                    f"({overlapping[0].date_from} - {overlapping[0].date_to})"
                )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id and self.partner_id.user_id:
            self.user_id = self.partner_id.user_id

    @api.onchange('template_id')  
    def _onchange_template_id(self):
        if not (self.template_id and self.partner_id):
            return
            
        if self._origin.id and self.template_id == self._origin.template_id:
            return
            
        self.line_ids = [(5, 0, 0)]
        lines = []
        
        for template_line in self.template_id.sale_order_template_line_ids:
            if not template_line.product_id or template_line.display_type:
                continue
                
            price = self._get_product_price(template_line)
            lines.append((0, 0, {
                'product_id': template_line.product_id.id,
                'quantity': template_line.product_uom_qty or 1.0,
                'price_unit': price,
            }))
        
        self.line_ids = lines
    
    def _get_product_price(self, template_line):
        pricelist = self.partner_id.property_product_pricelist
        if pricelist:
            try:
                return pricelist.get_product_price(
                    template_line.product_id, 1.0, self.partner_id,
                    date=fields.Date.today()
                )
            except:
                pass
        return template_line.product_id.list_price
