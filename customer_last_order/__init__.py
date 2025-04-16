from . import models


def post_init_hook(env):
    query = """
        WITH combined_orders AS (
            SELECT 
                so.partner_id,
                so.date_order,
                so.name AS order_reference
            FROM sale_order so
            WHERE so.state IN ('sale', 'done')
            
            UNION ALL
            
            SELECT 
                po.partner_id,
                po.date_order,
                po.pos_reference AS order_reference
            FROM pos_order po
            WHERE po.state IN ('paid', 'done', 'invoiced')
        ),
        latest_orders AS (
            SELECT 
                partner_id,
                MAX(date_order) AS max_date
            FROM combined_orders
            GROUP BY partner_id
        )
        SELECT 
            co.partner_id,
            co.date_order,
            co.order_reference
        FROM combined_orders co
        JOIN latest_orders lo 
            ON co.partner_id = lo.partner_id AND co.date_order = lo.max_date
    """

    env.cr.execute(query)
    results = env.cr.fetchall()

    for partner_id, date_order, order_ref in results:
        partner = env["res.partner"].browse(partner_id)
        partner.write(
            {
                "customer_last_order_date": date_order,
                "customer_last_order_ref": order_ref,
            }
        )
