from . import models
from . import report
from . import wizards

from odoo import tools


def _pre_init_marin(env):
    env.cr.execute(
        """
        SELECT setval('"public"."res_partner_category_id_seq"', 100, true);
        SELECT setval('"public"."uom_category_id_seq"', 100, true);
        SELECT setval('"public"."uom_uom_id_seq"', 100, true);
        """
    )
