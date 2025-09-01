from . import models
from . import wizard


def _documents_product_asset_post_init(env):
    env["res.company"].search(
        [("documents_folder_fleet_id", "=", False)]
    ).documents_folder_fleet_id = env.ref(
        "documents_product_asset.document_folder_fleet"
    )
