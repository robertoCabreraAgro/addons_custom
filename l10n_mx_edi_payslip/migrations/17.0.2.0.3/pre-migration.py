import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    remove_sua_idse_report_lines(cr)


def remove_sua_idse_report_lines(cr):
    """Remove the SUA & IDSE report lines, because will be created again with the correct xml_id"""
    env = api.Environment(cr, SUPERUSER_ID, {})

    reports = (
        env.ref("l10n_mx_edi_payslip.idse_report")
        | env.ref("l10n_mx_edi_payslip.idse_baja_report")
        | env.ref("l10n_mx_edi_payslip.idse_wage_report")
        | env.ref("l10n_mx_edi_payslip.sua_report")
        | env.ref("l10n_mx_edi_payslip.sua_affiliation_report")
        | env.ref("l10n_mx_edi_payslip.sua_move_report")
    )
    cr.execute(
        """
        DELETE FROM
            account_report_column
        WHERE
            report_id in %s;
        """,
        (tuple(reports.ids),),
    )
    _logger.info("%d report columns were removed.", cr.rowcount)

    cr.execute(
        """
        DELETE FROM
            account_report_expression
        WHERE
            report_line_id in %s;
        """,
        (tuple(reports.line_ids.ids),),
    )
    _logger.info("%d report expressions were removed.", cr.rowcount)
