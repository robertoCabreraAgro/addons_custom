# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_init_hook(env):
    """Post-installation hook to set up initial configurations."""
    # Activate EDI cron if needed
    cron = env.ref("account_edi.ir_cron_edi_network", raise_if_not_found=False)
    if cron and not cron.active:
        cron.active = True

    # Set up default workflows
    _setup_default_workflows(env)


def _setup_default_workflows(env):
    """Set up default EDI workflows."""
    # This will be implemented as workflows are developed
    pass
