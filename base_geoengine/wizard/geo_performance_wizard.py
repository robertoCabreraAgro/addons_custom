import logging

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class GeoPerformanceWizard(models.TransientModel):
    """Wizard for analyzing GeoEngine performance and generating reports.

    Provides tools for monitoring spatial operation performance, cache effectiveness,
    and database optimization recommendations.
    """

    _name = "geo.performance.wizard"
    _description = "GeoEngine Performance Analysis"

    # Analysis period
    analysis_period = fields.Selection(
        selection=[
            ("1h", "Last Hour"),
            ("24h", "Last 24 Hours"),
            ("7d", "Last 7 Days"),
            ("30d", "Last 30 Days"),
            ("custom", "Custom Period"),
        ],
        string="Analysis Period",
        required=True,
        default="24h",
    )
    date_from = fields.Datetime(
        string="From Date",
        default=lambda self: fields.Datetime.now() - timedelta(hours=24),
    )
    date_to = fields.Datetime(string="To Date", default=fields.Datetime.now)

    # Analysis options
    include_cache_stats = fields.Boolean(
        string="Include Cache Statistics",
        default=True,
        help="Analyze spatial cache performance",
    )
    include_query_analysis = fields.Boolean(
        string="Include Query Analysis",
        default=True,
        help="Analyze spatial query performance",
    )
    include_index_recommendations = fields.Boolean(
        string="Include Index Recommendations",
        default=True,
        help="Analyze spatial indexes and provide recommendations",
    )

    # Results
    analysis_result = fields.Html(string="Analysis Results", readonly=True)
    recommendations = fields.Text(string="Performance Recommendations", readonly=True)

    @api.onchange("analysis_period")
    def _onchange_analysis_period(self):
        """Update date range based on selected period."""
        if self.analysis_period == "1h":
            self.date_from = fields.Datetime.now() - timedelta(hours=1)
            self.date_to = fields.Datetime.now()
        elif self.analysis_period == "24h":
            self.date_from = fields.Datetime.now() - timedelta(hours=24)
            self.date_to = fields.Datetime.now()
        elif self.analysis_period == "7d":
            self.date_from = fields.Datetime.now() - timedelta(days=7)
            self.date_to = fields.Datetime.now()
        elif self.analysis_period == "30d":
            self.date_from = fields.Datetime.now() - timedelta(days=30)
            self.date_to = fields.Datetime.now()

    def action_analyze_performance(self):
        """Run performance analysis and generate report.

        Returns:
            dict: Action to reload the wizard with results.
        """
        self.ensure_one()

        try:
            analysis_html = self._generate_performance_report()
            recommendations = self._generate_recommendations()

            self.write(
                {"analysis_result": analysis_html, "recommendations": recommendations}
            )

            return {
                "type": "ir.actions.act_window",
                "res_model": "geo.performance.wizard",
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
                "context": {"default_show_results": True},
            }

        except Exception as e:
            raise UserError(_("Performance analysis failed: %s") % str(e))

    def _generate_performance_report(self):
        """Generate HTML performance analysis report.

        Returns:
            str: HTML formatted performance report.
        """
        report_parts = ["<h3>GeoEngine Performance Analysis</h3>"]

        # Analysis period info
        report_parts.append(
            f"<p><strong>Analysis Period:</strong> {self.date_from} to {self.date_to}</p>"
        )

        if self.include_cache_stats:
            report_parts.append(self._analyze_cache_performance())

        if self.include_query_analysis:
            report_parts.append(self._analyze_query_performance())

        if self.include_index_recommendations:
            report_parts.append(self._analyze_spatial_indexes())

        return "<br/>".join(report_parts)

    def _analyze_cache_performance(self):
        """Analyze spatial cache performance.

        Returns:
            str: HTML section for cache analysis.
        """
        geo_service = self.env["geo.service"]
        stats = geo_service.get_cache_stats()

        cache_html = [
            "<h4>Cache Performance</h4>",
            f"<p><strong>Transform Cache:</strong> {stats['transform_cache_size']} entries</p>",
            f"<p><strong>Operation Cache:</strong> {stats['operation_cache_size']} entries</p>",
            f"<p><strong>Search Cache:</strong> {stats['search_cache_size']} entries</p>",
            f"<p><strong>Cache Hit Ratio:</strong> {stats['hit_ratio']:.1%}</p>",
            f"<p><strong>Total Hits:</strong> {stats['cache_hits']}</p>",
            f"<p><strong>Total Misses:</strong> {stats['cache_misses']}</p>",
        ]

        # Cache health assessment
        if stats["hit_ratio"] > 0.8:
            cache_html.append(
                "<p style='color: green;'><strong>✓ Cache Performance: Excellent</strong></p>"
            )
        elif stats["hit_ratio"] > 0.6:
            cache_html.append(
                "<p style='color: orange;'><strong>⚠ Cache Performance: Good</strong></p>"
            )
        else:
            cache_html.append(
                "<p style='color: red;'><strong>✗ Cache Performance: Needs Improvement</strong></p>"
            )

        return "".join(cache_html)

    def _analyze_query_performance(self):
        """Analyze spatial query performance from database logs.

        Returns:
            str: HTML section for query analysis.
        """
        # This would ideally analyze PostgreSQL logs for spatial queries
        # For now, provide basic analysis based on configuration

        config = self.env["ir.config_parameter"].sudo()
        log_operations = (
            config.get_param("base_geoengine.log_operations", "False") == "True"
        )

        query_html = ["<h4>Query Performance Analysis</h4>"]

        if log_operations:
            query_html.extend(
                [
                    "<p><strong>Query Logging:</strong> Enabled ✓</p>",
                    "<p><em>Note: Detailed query analysis requires PostgreSQL log analysis tools.</em></p>",
                    "<p>Check server logs for spatial operation performance details.</p>",
                ]
            )
        else:
            query_html.extend(
                [
                    "<p><strong>Query Logging:</strong> Disabled</p>",
                    "<p style='color: orange;'><strong>⚠ Enable query logging in settings for detailed analysis</strong></p>",
                ]
            )

        return "".join(query_html)

    def _analyze_spatial_indexes(self):
        """Analyze spatial indexes and provide recommendations.

        Returns:
            str: HTML section for spatial index analysis.
        """
        cr = self.env.cr

        # Query for geometry columns and their indexes
        cr.execute(
            """
            SELECT 
                gc.f_table_name,
                gc.f_geometry_column,
                gc.type,
                gc.srid,
                CASE WHEN pi.indexname IS NOT NULL THEN 'Yes' ELSE 'No' END as has_index
            FROM geometry_columns gc
            LEFT JOIN pg_indexes pi ON (
                pi.tablename = gc.f_table_name 
                AND pi.indexname LIKE '%' || gc.f_geometry_column || '%'
                AND pi.indexdef LIKE '%gist%'
            )
            ORDER BY gc.f_table_name, gc.f_geometry_column
            """
        )

        results = cr.fetchall()

        index_html = [
            "<h4>Spatial Index Analysis</h4>",
            "<table border='1' style='border-collapse: collapse; width: 100%;'>",
            "<tr style='background-color: #f0f0f0;'>",
            "<th>Table</th><th>Column</th><th>Type</th><th>SRID</th><th>Has Index</th>",
            "</tr>",
        ]

        missing_indexes = []

        for row in results:
            table, column, geom_type, srid, has_index = row
            row_color = "#ffe6e6" if has_index == "No" else "#e6ffe6"

            index_html.append(
                f"<tr style='background-color: {row_color};'>"
                f"<td>{table}</td><td>{column}</td><td>{geom_type}</td>"
                f"<td>{srid}</td><td>{has_index}</td></tr>"
            )

            if has_index == "No":
                missing_indexes.append((table, column))

        index_html.append("</table>")

        if missing_indexes:
            index_html.append(
                "<p style='color: red;'><strong>⚠ Missing Spatial Indexes:</strong></p>"
            )
            index_html.append("<ul>")
            for table, column in missing_indexes:
                index_html.append(f"<li>{table}.{column}</li>")
            index_html.append("</ul>")
        else:
            index_html.append(
                "<p style='color: green;'><strong>✓ All geometry columns have spatial indexes</strong></p>"
            )

        return "".join(index_html)

    def _generate_recommendations(self):
        """Generate performance improvement recommendations.

        Returns:
            str: Text recommendations for performance improvements.
        """
        recommendations = []

        # Check cache configuration
        config = self.env["ir.config_parameter"].sudo()
        cache_enabled = (
            config.get_param("base_geoengine.enable_cache", "True") == "True"
        )

        if not cache_enabled:
            recommendations.append("• Enable spatial caching for better performance")

        # Check cache settings
        geo_service = self.env["geo.service"]
        stats = geo_service.get_cache_stats()

        if stats["hit_ratio"] < 0.6:
            recommendations.append(
                "• Increase cache timeout or max entries to improve cache hit ratio"
            )

        # Check logging settings
        log_operations = (
            config.get_param("base_geoengine.log_operations", "False") == "True"
        )
        if not log_operations:
            recommendations.append(
                "• Enable spatial operation logging for detailed performance monitoring"
            )

        # Check geometry validation
        validate_geometry = (
            config.get_param("base_geoengine.validate_geometry", "True") == "True"
        )
        if validate_geometry:
            recommendations.append(
                "• Consider disabling geometry validation in production for better performance"
            )

        # Database recommendations
        recommendations.extend(
            [
                "• Regularly run VACUUM ANALYZE on tables with geometry columns",
                "• Monitor PostGIS extension updates for performance improvements",
                "• Consider partitioning large tables with geometry data",
                "• Use appropriate SRID for your geographic region to minimize transformations",
            ]
        )

        return (
            "\n".join(recommendations)
            if recommendations
            else "No specific recommendations at this time. System performance appears optimal."
        )

    def action_apply_recommendations(self):
        """Apply automated performance optimizations.

        Returns:
            dict: Success notification action.
        """
        self.ensure_one()

        applied_changes = []

        # Enable caching if disabled
        config = self.env["ir.config_parameter"].sudo()
        if config.get_param("base_geoengine.enable_cache", "True") != "True":
            config.set_param("base_geoengine.enable_cache", "True")
            applied_changes.append("Enabled spatial caching")

        # Create missing spatial indexes
        self._create_missing_indexes()
        applied_changes.append("Checked and created missing spatial indexes")

        # Clear cache to start fresh
        geo_service = self.env["geo.service"]
        geo_service.clear_geo_cache()
        applied_changes.append("Cleared spatial caches")

        message = "Applied optimizations:\n" + "\n".join(
            f"• {change}" for change in applied_changes
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Optimizations Applied"),
                "message": message,
                "sticky": True,
            },
        }

    def _create_missing_indexes(self):
        """Create missing spatial indexes."""
        cr = self.env.cr

        # Find geometry columns without GIST indexes
        cr.execute(
            """
            SELECT 
                gc.f_table_name,
                gc.f_geometry_column
            FROM geometry_columns gc
            LEFT JOIN pg_indexes pi ON (
                pi.tablename = gc.f_table_name 
                AND pi.indexname LIKE '%' || gc.f_geometry_column || '%'
                AND pi.indexdef LIKE '%gist%'
            )
            WHERE pi.indexname IS NULL
            """
        )

        missing_indexes = cr.fetchall()

        for table, column in missing_indexes:
            try:
                index_name = f"{table}_{column}_gist_idx"
                cr.execute(
                    f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table}" USING GIST ("{column}")'
                )
                logger.info(
                    "Created spatial index %s on %s.%s", index_name, table, column
                )
            except Exception as e:
                logger.error(
                    "Failed to create spatial index on %s.%s: %s", table, column, e
                )
