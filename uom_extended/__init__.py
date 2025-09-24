import logging
from . import models
from . import wizard

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Pre-warm UoM reference cache after module installation.

    This improves performance by caching commonly used UoM references
    that are expensive to resolve via env.ref() calls.
    """
    template_model = env["product.template"]

    # Pre-warm cache for standard UoM references
    standard_uom_refs = [
        "uom.product_uom_yard",
        "uom.product_uom_meter",
        "uom.product_uom_mile",
        "uom.product_uom_km",
        "uom.product_uom_square_foot",
        "uom.product_uom_square_meter",
    ]

    # Pre-warm cache for extended UoM references
    extended_uom_refs = [
        "uom_extended.product_uom_hp",
        "uom_extended.product_uom_kw",
        "uom_extended.product_uom_miles_per_galon",
        "uom_extended.product_uom_km_per_liter",
    ]

    # Cache standard UoMs (these should always exist)
    for ref in standard_uom_refs:
        try:
            template_model._get_cached_uom_ref(ref)
        except ValueError as e:
            _logger.warning("Standard UoM reference '%s' not found during cache pre-warming: %s", ref, e)

    # Cache extended UoMs (these are created by our module)
    for ref in extended_uom_refs:
        try:
            template_model._get_cached_uom_ref(ref)
        except ValueError as e:
            _logger.info("Extended UoM reference '%s' not yet available during cache pre-warming: %s", ref, e)
