import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)


class GeoSetupWizard(models.TransientModel):
    """Wizard for initial GeoEngine setup and configuration.

    Guides users through the initial configuration of GeoEngine including
    spatial reference systems, performance settings, and database optimization.
    """

    _name = "geo.setup.wizard"
    _description = "GeoEngine Setup Wizard"

    # Setup steps
    current_step = fields.Selection(
        selection=[
            ("welcome", "Welcome"),
            ("spatial_config", "Spatial Configuration"),
            ("performance_config", "Performance Settings"),
            ("database_setup", "Database Setup"),
            ("completion", "Setup Complete"),
        ],
        string="Current Step",
        required=True,
        default="welcome",
    )

    # Welcome step
    setup_type = fields.Selection(
        [
            ("quick", "Quick Setup (Recommended)"),
            ("advanced", "Advanced Setup"),
            ("custom", "Custom Configuration"),
        ],
        string="Setup Type",
        default="quick",
    )

    # Spatial configuration
    region = fields.Selection(
        [
            ("north_america", "North America"),
            ("europe", "Europe"),
            ("asia_pacific", "Asia Pacific"),
            ("south_america", "South America"),
            ("africa", "Africa"),
            ("global", "Global/Mixed"),
            ("custom", "Custom Configuration"),
        ],
        string="Primary Region",
        default="global",
    )

    default_srid = fields.Integer(
        string="Default SRID",
        default=3857,
        help="Spatial Reference System for data storage",
    )
    display_srid = fields.Integer(
        string="Display SRID",
        default=4326,
        help="Spatial Reference System for display (usually WGS84: 4326)",
    )
    coordinate_precision = fields.Integer(
        string="Coordinate Precision", default=6, help="Decimal places for coordinates"
    )

    # Performance settings
    enable_cache = fields.Boolean(
        string="Enable Spatial Caching",
        default=True,
        help="Cache spatial operations for better performance",
    )
    cache_timeout = fields.Integer(
        string="Cache Timeout (minutes)",
        default=60,
        help="How long to keep cached results",
    )
    max_cache_entries = fields.Integer(
        string="Max Cache Entries", default=1000, help="Maximum cached items"
    )
    max_geometry_size = fields.Integer(
        string="Max Geometry Size (MB)",
        default=1,
        help="Maximum geometry size in megabytes",
    )

    # Database settings
    create_spatial_indexes = fields.Boolean(
        string="Auto-create Spatial Indexes",
        default=True,
        help="Automatically create indexes for geometry fields",
    )
    validate_geometries = fields.Boolean(
        string="Validate Geometries",
        default=True,
        help="Validate geometry data before saving",
    )
    enable_monitoring = fields.Boolean(
        string="Enable Performance Monitoring",
        default=True,
        help="Monitor cache and query performance",
    )

    # Results
    setup_summary = fields.Html(string="Setup Summary", readonly=True)
    setup_complete = fields.Boolean(string="Setup Complete", default=False)

    @api.onchange("region")
    def _onchange_region(self):
        """Update SRID settings based on selected region."""
        region_configs = {
            "north_america": {"default_srid": 3857, "display_srid": 4326},
            "europe": {"default_srid": 3857, "display_srid": 4326},
            "asia_pacific": {"default_srid": 3857, "display_srid": 4326},
            "south_america": {"default_srid": 3857, "display_srid": 4326},
            "africa": {"default_srid": 3857, "display_srid": 4326},
            "global": {"default_srid": 3857, "display_srid": 4326},
        }

        if self.region in region_configs:
            config = region_configs[self.region]
            self.default_srid = config["default_srid"]
            self.display_srid = config["display_srid"]

    @api.onchange("setup_type")
    def _onchange_setup_type(self):
        """Apply preset configurations based on setup type."""
        if self.setup_type == "quick":
            # Optimized defaults for quick setup
            self.enable_cache = True
            self.cache_timeout = 60
            self.max_cache_entries = 1000
            self.max_geometry_size = 1
            self.create_spatial_indexes = True
            self.validate_geometries = True
            self.enable_monitoring = True

        elif self.setup_type == "advanced":
            # Performance-focused settings
            self.enable_cache = True
            self.cache_timeout = 120
            self.max_cache_entries = 5000
            self.max_geometry_size = 5
            self.create_spatial_indexes = True
            self.validate_geometries = False  # Disabled for performance
            self.enable_monitoring = True

    def action_next_step(self):
        """Move to the next setup step.

        Returns:
            dict: Action to reload wizard with next step.
        """
        self.ensure_one()

        step_sequence = [
            "welcome",
            "spatial_config",
            "performance_config",
            "database_setup",
            "completion",
        ]
        current_index = step_sequence.index(self.current_step)

        if current_index < len(step_sequence) - 1:
            next_step = step_sequence[current_index + 1]

            # Validate current step before proceeding
            self._validate_current_step()

            self.current_step = next_step

            if next_step == "completion":
                self._apply_configuration()

        return self._return_wizard_action()

    def action_previous_step(self):
        """Move to the previous setup step.

        Returns:
            dict: Action to reload wizard with previous step.
        """
        self.ensure_one()

        step_sequence = [
            "welcome",
            "spatial_config",
            "performance_config",
            "database_setup",
            "completion",
        ]
        current_index = step_sequence.index(self.current_step)

        if current_index > 0:
            self.current_step = step_sequence[current_index - 1]

        return self._return_wizard_action()

    def action_skip_setup(self):
        """Skip setup and use default configuration.

        Returns:
            dict: Action to close wizard.
        """
        self.ensure_one()

        # Apply minimal default configuration
        self._apply_minimal_config()

        return {"type": "ir.actions.act_window_close"}

    def action_finish_setup(self):
        """Complete the setup process.

        Returns:
            dict: Action to close wizard or show success message.
        """
        self.ensure_one()

        if not self.setup_complete:
            self._apply_configuration()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Setup Complete"),
                "message": _(
                    "GeoEngine has been successfully configured and is ready to use."
                ),
                "sticky": False,
            },
        }

    def _validate_current_step(self):
        """Validate the current step configuration.

        Raises:
            ValidationError: When step validation fails.
        """
        if self.current_step == "spatial_config":
            if self.default_srid <= 0 or self.display_srid <= 0:
                raise ValidationError(_("SRID values must be positive integers"))
            if not 0 <= self.coordinate_precision <= 15:
                raise ValidationError(
                    _("Coordinate precision must be between 0 and 15")
                )

        elif self.current_step == "performance_config":
            if self.cache_timeout <= 0:
                raise ValidationError(_("Cache timeout must be positive"))
            if self.max_cache_entries <= 0:
                raise ValidationError(_("Max cache entries must be positive"))
            if self.max_geometry_size <= 0:
                raise ValidationError(_("Max geometry size must be positive"))

    def _apply_configuration(self):
        """Apply the configured settings to the system."""
        config_params = self.env["ir.config_parameter"].sudo()

        # Spatial configuration
        config_params.set_param("base_geoengine.default_srid", str(self.default_srid))
        config_params.set_param("base_geoengine.display_srid", str(self.display_srid))
        config_params.set_param(
            "base_geoengine.coordinate_precision", str(self.coordinate_precision)
        )

        # Performance settings
        config_params.set_param("base_geoengine.enable_cache", str(self.enable_cache))
        config_params.set_param(
            "base_geoengine.cache_timeout", str(self.cache_timeout * 60)
        )  # Convert to seconds
        config_params.set_param(
            "base_geoengine.max_cache_entries", str(self.max_cache_entries)
        )
        config_params.set_param(
            "base_geoengine.max_geometry_size",
            str(self.max_geometry_size * 1024 * 1024),
        )  # Convert to bytes

        # Database settings
        config_params.set_param(
            "base_geoengine.auto_spatial_indexes", str(self.create_spatial_indexes)
        )
        config_params.set_param(
            "base_geoengine.validate_geometry", str(self.validate_geometries)
        )
        config_params.set_param(
            "base_geoengine.monitor_cache", str(self.enable_monitoring)
        )

        # Generate setup summary
        self.setup_summary = self._generate_setup_summary()
        self.setup_complete = True

        # Create initial spatial indexes if requested
        if self.create_spatial_indexes:
            self._create_initial_indexes()

        logger.info("GeoEngine configuration applied successfully")

    def _apply_minimal_config(self):
        """Apply minimal default configuration."""
        config_params = self.env["ir.config_parameter"].sudo()

        # Set basic defaults
        config_params.set_param("base_geoengine.default_srid", "3857")
        config_params.set_param("base_geoengine.display_srid", "4326")
        config_params.set_param("base_geoengine.enable_cache", "True")
        config_params.set_param("base_geoengine.validate_geometry", "True")

        logger.info("GeoEngine minimal configuration applied")

    def _generate_setup_summary(self):
        """Generate HTML summary of applied configuration.

        Returns:
            str: HTML formatted setup summary.
        """
        summary_parts = [
            "<h3>GeoEngine Configuration Summary</h3>",
            f"<p><strong>Setup Type:</strong> {dict(self._fields['setup_type'].selection)[self.setup_type]}</p>",
            f"<p><strong>Region:</strong> {dict(self._fields['region'].selection)[self.region]}</p>",
            "<h4>Spatial Reference Systems</h4>",
            f"<p>Default SRID: {self.default_srid}</p>",
            f"<p>Display SRID: {self.display_srid}</p>",
            f"<p>Coordinate Precision: {self.coordinate_precision} decimal places</p>",
            "<h4>Performance Settings</h4>",
            f"<p>Spatial Caching: {'Enabled' if self.enable_cache else 'Disabled'}</p>",
            f"<p>Cache Timeout: {self.cache_timeout} minutes</p>",
            f"<p>Max Cache Entries: {self.max_cache_entries}</p>",
            f"<p>Max Geometry Size: {self.max_geometry_size} MB</p>",
            "<h4>Database Settings</h4>",
            f"<p>Auto-create Indexes: {'Yes' if self.create_spatial_indexes else 'No'}</p>",
            f"<p>Validate Geometries: {'Yes' if self.validate_geometries else 'No'}</p>",
            f"<p>Performance Monitoring: {'Enabled' if self.enable_monitoring else 'Disabled'}</p>",
        ]

        return "".join(summary_parts)

    def _create_initial_indexes(self):
        """Create spatial indexes for existing geometry columns."""
        try:
            cr = self.env.cr
            cr.execute(
                """
                SELECT f_table_name, f_geometry_column
                FROM geometry_columns
            """
            )

            geometry_columns = cr.fetchall()
            created_indexes = 0

            for table, column in geometry_columns:
                try:
                    index_name = f"{table}_{column}_gist_idx"
                    cr.execute(
                        f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table}" USING GIST ("{column}")'
                    )
                    created_indexes += 1
                except Exception as e:
                    logger.warning(
                        "Could not create index for %s.%s: %s", table, column, e
                    )

            logger.info("Created %d spatial indexes during setup", created_indexes)

        except Exception as e:
            logger.error("Failed to create initial spatial indexes: %s", e)

    def _return_wizard_action(self):
        """Return action to reload the wizard.

        Returns:
            dict: Wizard reload action.
        """
        return {
            "type": "ir.actions.act_window",
            "res_model": "geo.setup.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
