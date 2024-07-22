from odoo import models, tools


class PurchaseBillUnion(models.Model):
    _inherit = "purchase.bill.union"

    def init(self):
        tools.drop_view_if_exists(self.env.cr, "purchase_bill_union")
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW purchase_bill_union AS (
                SELECT
                    id, name, ref as reference, partner_id, date, amount_untaxed as amount, currency_id, company_id,
                    id as vendor_bill_id, NULL as purchase_order_id
                FROM account_move
                WHERE
                    move_type='in_invoice' and state = 'posted'
                UNION
                    SELECT
                        -id, name, partner_ref as reference, partner_id, date_order::date as date,
                        amount_untaxed as amount, currency_id, company_id,
                        NULL as vendor_bill_id, id as purchase_order_id
                    FROM purchase_order
                    WHERE
                        state in ('purchase', 'done') AND
                        invoice_status in ('partially', 'to invoice', 'no')
            )
            """
        )
