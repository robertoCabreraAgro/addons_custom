from odoo import api, fields, models


class HrEmployeeAlimony(models.Model):
    _name = "hr.employee.alimony"
    _description = "Allow define the alimony records for employees"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Order", required=True, tracking=True)
    court = fields.Char(tracking=True)
    number = fields.Char(tracking=True, required=True)
    discount_type = fields.Selection(
        selection=[
            ("percentage_wage", "Percentage over salary"),
            ("percentage_perceptions_ISR", "Percentage over perceptions less ISR and Social Security"),
            ("amount_fixed", "Amount fixed"),
            ("percentage_over_net", "Percentage over net"),
            ("percentage_perceptions", "Percentage over perceptions"),
            ("percentage_perceptions_ISR_mortgages", "Percentage over perceptions less ISR and Mortgages"),
            (
                "percentage_perceptions_ISR_mortgages_ss",
                "Percentage over perceptions less ISR, Social Security and Mortgages",
            ),
            ("percentage_christmas", "Percentage over Christmas bonus"),
            ("percentage_christmas_isr", "Percentage over Christmas bonus less ISR"),
            ("percentage_christmas_holidays", "Percentage over Christmas bonus and holidays"),
            ("amount_fixed_christmas", "Fixed over Christmas bonus"),
        ],
        required=True,
    )
    discount_amount = fields.Float(
        "Discount/Percent Amount",
        tracking=True,
        required=True,
        help="If this alimony is based on un amount, indicate the amount by each payment period.",
    )
    date_from = fields.Date(tracking=True, required=True)
    date_to = fields.Date(tracking=True)
    partner_id = fields.Many2one("res.partner", "Beneficiary", tracking=True)
    employee_id = fields.Many2one("hr.employee", tracking=True)
    payment_method_id = fields.Many2one("l10n_mx_edi.payment.method", "Payment Way", tracking=True)
    notes = fields.Text(tracking=True)
    increase_based_on = fields.Selection(
        selection=[
            ("uma", "UMA"),
            ("vsm", "VSM"),
            ("annual", "Annual"),
        ],
        string="Base for Increase",
        help="If the alimony must increase, indicate base in with will be increased.",
    )
    amount_annual_increase = fields.Float("Amount for annual increase")
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="Is this alimony being considered?",
    )

    @api.model
    def update_alimony(self):
        today = fields.datetime.now()
        for record in self.search([("increase_based_on", "=", "annual")]):
            if (
                record.date_from.month == today.month
                and record.date_from.day == today.day
                and record.date_from.year != today.year
            ):
                record.discount_amount += record.amount_annual_increase
