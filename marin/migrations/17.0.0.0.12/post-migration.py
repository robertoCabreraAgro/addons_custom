def migrate(cr, version):
    set_use_expiration_date(cr)


def set_use_expiration_date(cr):
    """Set the use of expiration date to all products that are tracked by lots."""
    query = """
        UPDATE
            product_template
        SET
            use_expiration_date = true
        WHERE
            tracking = 'lot';
    """
    cr.execute(query)
