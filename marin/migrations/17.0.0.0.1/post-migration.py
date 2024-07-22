def migrate(cr, version):
    remove_modules(cr)


def remove_modules(cr):
    # Removing modules that are not required anymore
    query = """
        DELETE FROM
            ir_module_module
        WHERE
            name in (
                'base_season',
                'muk_product',
                'marin_l10n_mx_edi_payslip'
            )
    """
    cr.execute(query)
