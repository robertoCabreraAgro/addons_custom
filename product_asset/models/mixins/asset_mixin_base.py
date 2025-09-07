from odoo import api, fields, models, _


class AssetMixinBase(models.AbstractModel):
    """Base mixin for asset-related functionality

    This mixin provides core asset fields and functionality that are
    common to all asset types. It includes asset identification,
    status tracking, and basic lifecycle management.
    """

    _name = "asset.mixin.base"
    _description = "Asset Base Mixin"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    # Asset type and identification
    asset_type = fields.Selection(
        selection=[
            ("equipment", "Equipment"),
            ("machinery", "Machinery"),
            ("product", "Product"),
            ("property", "Property"),
            ("vehicle", "Vehicle"),
        ],
        string="Asset Type",
        help="Type of asset being tracked",
    )
    type_name = fields.Char(
        string="Type Name",
        compute="_compute_type_name",
        help="Human-readable name for the asset type",
    )

    # Location and basic info
    location = fields.Char(
        string="Location",
        help="Physical location of the asset (garage, warehouse, etc.)",
    )
    brand_new = fields.Boolean(
        string="Brand New",
        default=True,
        help="Indicates if this asset was acquired as brand new",
    )

    # Lifecycle dates
    date_acquisition = fields.Date(
        string="Acquisition Date",
        copy=False,
        tracking=True,
        help="Date when the asset was acquired",
    )
    date_write_off = fields.Date(
        string="Write-off Date",
        copy=False,
        tracking=True,
        help="Date when the asset was written off or disposed",
    )

    # Log management
    log_ids = fields.One2many(
        comodel_name="product.asset.log",
        inverse_name="asset_id",
        string="Asset Logs",
        help="All logs and history for this asset",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("product_id", "asset_type")
    def _compute_type_name(self):
        """Compute human-readable type name based on asset type and product tracking"""
        for record in self:
            if record.product_id.tracking == "serial":
                record.type_name = _("Serial Number")
            elif record.product_id.tracking == "lot":
                record.type_name = _("Lot Number")
            elif record.asset_type == "vehicle":
                record.type_name = _("Vehicle")
            elif record.asset_type == "equipment":
                record.type_name = _("Equipment")
            elif record.asset_type == "machinery":
                record.type_name = _("Machine")
            elif record.asset_type == "property":
                record.type_name = _("Property")
            else:
                record.type_name = _("Product")

    # ------------------------------------------------------------
    # HELPER METHODS
    # ------------------------------------------------------------

    def _get_asset_display_name(self):
        """Get a formatted display name for the asset"""
        self.ensure_one()
        parts = []

        if self.type_name:
            parts.append(self.type_name)

        if hasattr(self, "name") and self.name:
            parts.append(self.name)
        elif hasattr(self, "license_plate") and self.license_plate:
            parts.append(self.license_plate)

        return " - ".join(parts) if parts else _("Asset")

    def _create_log_entry(self, product_id, description, **kwargs):
        """Helper method to create a log entry for this asset

        Args:
            product_id: Product ID for the log entry
            description: Description of the log entry
            **kwargs: Additional fields for the log entry
        """
        self.ensure_one()
        log_vals = {
            "asset_id": self.id,
            "product_id": product_id,
            "description": description,
            "date": fields.Date.today(),
            **kwargs,
        }
        return self.env["product.asset.log"].create(log_vals)
