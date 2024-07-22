from . import models


def _pre_init_hook(env):
    env.cr.execute(
        """
        UPDATE
            ir_model_data
        SET
            noupdate = true,
            name = 'partner_syngenta',
            module = 'syngenta_edi'
        WHERE
            model='res.partner'
            AND module = '__custom__'
            AND name = 'syngenta'
    """
    )
