import logging

from psycopg2.extensions import AsIs

from odoo import tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    remove_old_field(cr)


def remove_old_field(cr):
    """Remove the use of l10n_mx_edi_date_** in payroll.

    Use secondary_** fields added in Payroll Dual Period (hr_payroll_dual_period)
    """

    def _update_fields(table, old_column, new_column):
        if tools.column_exists(cr, table, old_column) and tools.column_exists(
            cr, table, new_column
        ):
            _logger.info(
                "Replace the use of column `%s` from the table `%s` to colum `%s`",
                old_column,
                table,
                new_column,
            )

            update_query = """
                UPDATE %s
                SET %s=%s
                WHERE %s IS NOT NULL
            """
            cr.execute(
                update_query,
                (AsIs(table), AsIs(new_column), AsIs(old_column), AsIs(old_column)),
            )

            _logger.info(
                "%d companies were updated to use the `%s` column instead of `%s` column",
                cr.rowcount,
                new_column,
                old_column,
            )

    table = "hr_payslip"
    old_column = "l10n_mx_edi_date_from"
    new_column = "secondary_date_from"
    _update_fields(table, old_column, new_column)

    table = "hr_payslip"
    old_column = "l10n_mx_edi_date_to"
    new_column = "secondary_date_to"
    _update_fields(table, old_column, new_column)

    table = "hr_payslip_run"
    old_column = "l10n_mx_edi_date_start"
    new_column = "secondary_date_from"
    _update_fields(table, old_column, new_column)

    table = "hr_payslip_run"
    old_column = "l10n_mx_edi_date_end"
    new_column = "secondary_date_to"
    _update_fields(table, old_column, new_column)
