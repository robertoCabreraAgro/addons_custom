import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    compute_store_fields(cr)


def compute_store_fields(cr):
    """Create and manually compute margin fields for pos.order and pos.order.line as they were changed to be
    storable."""
    _logger.info("Creating fields margin and margin_percent on pos_order")
    cr.execute(
        """
        ALTER TABLE pos_order
        ADD COLUMN IF NOT EXISTS is_total_cost_computed BOOLEAN,
        ADD COLUMN IF NOT EXISTS margin FLOAT,
        ADD COLUMN IF NOT EXISTS margin_percent FLOAT;
    """
    )

    _logger.info("Creating fields margin and margin_percent on pos_order_line")
    cr.execute(
        """
        ALTER TABLE pos_order_line
        ADD COLUMN IF NOT EXISTS margin FLOAT,
        ADD COLUMN IF NOT EXISTS margin_percent FLOAT;
    """
    )

    # _logger.info('Fill margin on pos_order_line')
    # cr.execute("""
    #     UPDATE
    #         pos_order_line
    #     SET
    #         margin = price_subtotal - total_cost
    # """)

    _logger.info("Fill margin and margin_percent on pos_order_line")
    cr.execute(
        """
        UPDATE
            pos_order_line
        SET
            margin = price_subtotal - total_cost,
            margin_percent = (
                CASE
                    WHEN price_subtotal IS NULL OR price_subtotal = 0
                    THEN 0
                    ELSE (price_subtotal - total_cost) / price_subtotal
                END
            )
    """
    )

    _logger.info("Fill margin AND margin_percent on pos_order")
    cr.execute(
        """
        WITH totals AS (
            SELECT
                order_id,
                SUM(margin) AS order_margin,
                SUM(price_subtotal) AS order_subtotal,
                BOOL_AND(is_total_cost_computed) AS order_is_computed
            FROM
                pos_order_line
            GROUP BY
                order_id
        )
        UPDATE
            pos_order
        SET
            margin = (
                CASE
                    WHEN order_is_computed
                    THEN order_margin
                    ELSE 0
                END
            ),
            margin_percent = (
                CASE
                    WHEN order_is_computed = False OR order_is_computed IS NULL
                        OR order_subtotal IS NULL OR order_subtotal = 0
                    THEN 0
                    ELSE order_margin / order_subtotal
                END
            ),
            is_total_cost_computed = order_is_computed
        FROM
            totals
        WHERE
            totals.order_id = pos_order.id
    """
    )
