from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    delete_view(cr)


def delete_view(cr):
    """The view is deleted because it no longer exists in code which used fields which also no longer exists
    and is causing trouble updating the module."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env.ref("marin.res_partner_view_buttons", False)
    if view:
        view.unlink()
