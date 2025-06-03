import logging

from odoo import api, SUPERUSER_ID
from odoo.tools import convert_file

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    update_crons_and_server_actions(cr)

def update_crons_and_server_actions(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})
    modules_to_convert_files = {
        "documents_l10n_mx_edi": [
            "data/ir_actions_server_data.xml",
            "data/ir_cron_data.xml",
        ],
    }
    for module_name, file_paths in modules_to_convert_files.items():
        for file_path in file_paths:
            convert_file(env, module_name, file_path, None)
            _logger.info("File '%s' from module '%s' reloaded.", file_path, module_name)
