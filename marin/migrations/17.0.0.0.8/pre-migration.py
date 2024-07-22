import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    change_xml_id(cr)


def change_xml_id(cr):
    """Update xml_id of record as it was changed."""
    _logger.info("Update xml_id of group Product cost user")

    name_mapping = [
        ("group_documents_password_user", "group_documents_password_readonly"),
        ("group_product_cost_user", "group_product_cost_manager"),
    ]
    query = """
        UPDATE
            ir_model_data
        SET
            name = '%s'
        WHERE
            module = 'marin'
            AND model = 'res.groups'
            AND name = '%s'
    """
    for name in name_mapping:
        cr.execute(query % (name[1], name[0]))
