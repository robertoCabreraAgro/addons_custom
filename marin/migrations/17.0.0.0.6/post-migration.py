from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    change_xml_ids(cr)
    uninstall_old_l10n_mx_documents(cr)


def uninstall_old_l10n_mx_documents(cr):
    """Uninstall custom module documents_l10n_mx_edi as it will be replaced."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env["ir.module.module"].search([("name", "=", "documents_l10n_mx_edi")])
    if module:
        module.button_uninstall()


def change_xml_ids(cr):
    """Update records xml ids, set the new module that will replace module documents_l10n_mx_edi."""
    query = """
        UPDATE
            ir_model_data
        SET
            module = 'l10n_mx_edi_document'
        WHERE
            module = 'documents_l10n_mx_edi'
            AND name in (
                'documents_l10n_mx_edi_facet_type',
                'documents_l10n_mx_edi_tag_ingreso',
                'documents_l10n_mx_edi_tag_egreso',
                'translado_tag',
                'documents_l10n_mx_edi_tag_reception',
                'documents_l10n_mx_edi_tag_nomina',
                'documents_l10n_mx_edi_tag_retencion'
            )
    """
    query2 = """
        UPDATE
            ir_model_data
        SET
            module = 'l10n_edi_document'
        WHERE
            module = 'documents_l10n_mx_edi'
            AND name in (
                'documents_l10n_mx_edi_folder',
                'edi_document_rule',
                'documents_replace_inbox_edi_document',
                'documents_add_documents_edi_document',
                'documents_incorrect_edi_folder',
                'documents_edi_not_found_folder',
                'documents_edi_automatic_partner_tag',
                'documents_edi_facet',
                'documents_edi_automatic_tag',
                'documents_edi_partner_requires_po_tag',
                'documents_edi_requires_po_tag',
                'documents_l10n_mx_edi_folder_received',
                'documents_l10n_mx_edi_folder_issued',
                'l10n_edi_document_documents_without_records',
                'documents_l10n_mx_edi_facet_fiscal_month',
                'l10n_edi_document_fiscal_month_01',
                'l10n_edi_document_fiscal_month_02',
                'l10n_edi_document_fiscal_month_03',
                'l10n_edi_document_fiscal_month_04',
                'l10n_edi_document_fiscal_month_05',
                'l10n_edi_document_fiscal_month_06',
                'l10n_edi_document_fiscal_month_07',
                'l10n_edi_document_fiscal_month_08',
                'l10n_edi_document_fiscal_month_09',
                'l10n_edi_document_fiscal_month_10',
                'l10n_edi_document_fiscal_month_11',
                'l10n_edi_document_fiscal_month_12'
            )
    """
    cr.execute(query)
    cr.execute(query2)
