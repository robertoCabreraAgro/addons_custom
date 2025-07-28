import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    update_group_relationships(cr)

def update_group_relationships(cr):
    """Update group_gps_tracking_reporting to include server actions group."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    try:
        # Get the reporting group and server actions group
        reporting_group = env.ref('gps_tracking.group_gps_tracking_reporting')
        server_actions_group = env.ref('gps_tracking.group_gps_tracking_server_actions_restricted')

        # Check if server actions group is already in implied_ids
        if server_actions_group not in reporting_group.implied_ids:
            # Add server actions group to implied_ids of reporting group
            reporting_group.write({
                'implied_ids': [(4, server_actions_group.id)]
            })
            _logger.info(
                "Added group '%s' to implied_ids of group '%s'",
                server_actions_group.name,
                reporting_group.name
            )
        else:
            _logger.info(
                "Group '%s' already in implied_ids of group '%s'",
                server_actions_group.name,
                reporting_group.name
            )

    except Exception as e:
        _logger.error("Failed to update group relationships: %s", str(e))
