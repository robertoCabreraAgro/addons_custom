# Copyright 2021 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import csv
from datetime import datetime, timedelta
from io import StringIO
from operator import attrgetter

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round


class AbcClassificationProfile(models.Model):
    _inherit = "abc.classification.profile"

    profile_type = fields.Selection(
        selection_add=[
            (
                "sale_stock",
                "Based on the count of delivered sale order line by product",
            )
        ],
        ondelete={"sale_stock": "cascade"},
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        "Warehouse",
        ondelete="cascade",
        default=lambda self: self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.user.company_id.id)], limit=1
        ),
    )
    interval_type = fields.Selection(
        [
            ("days", "Days"),
            ("seasons", "Seasons"),
        ],
        string="Interval Type",
        default="days",
        help="Choose how to define the time period for ABC classification: "
        "Days uses a fixed period from today, "
        "Seasons uses specific date ranges",
    )
    date_range_ids = fields.Many2many(
        "date.range",
        string="Seasons",
        domain="[('type_id.code', '=', 'AG'), ('active', '=', True)]",
        help="Select one or more agricultural seasons for ABC classification calculation",
    )

    @api.constrains("profile_type", "warehouse_id")
    def _check_warehouse_id(self):
        for rec in self:
            if rec.profile_type == "sale_stock" and not rec.warehouse_id:
                raise ValidationError(
                    self.env._(
                        "You must specify a warehouse for {profile_name}"
                    ).format(profile_name=rec.name)
                )

    @api.constrains("profile_type", "interval_type", "date_range_ids")
    def _check_date_range_ids(self):
        for rec in self:
            if rec.profile_type == "sale_stock" and rec.interval_type == "seasons":
                if not rec.date_range_ids:
                    raise ValidationError(
                        self.env._(
                            "At least one season must be selected when using seasons."
                        )
                    )
                # Verificar que al menos una estación esté activa
                active_ranges = rec.date_range_ids.filtered("active")
                if not active_ranges:
                    raise ValidationError(
                        self.env._("At least one selected season must be active.")
                    )

    @api.constrains("warehouse_id", "date_range_ids", "profile_type", "interval_type")
    def _check_warehouse_season_overlap(self):
        """Prevent overlapping seasons for the same warehouse."""
        for rec in self:
            if (
                rec.profile_type == "sale_stock"
                and rec.interval_type == "seasons"
                and rec.warehouse_id
                and rec.date_range_ids
            ):
                # Search for other profiles with same warehouse and overlapping date ranges
                domain = [
                    ("id", "!=", rec.id),
                    ("profile_type", "=", "sale_stock"),
                    ("interval_type", "=", "seasons"),
                    ("warehouse_id", "=", rec.warehouse_id.id),
                ]
                other_profiles = self.search(domain)

                for other_profile in other_profiles:
                    if not other_profile.date_range_ids:
                        continue

                    # Check for overlapping date ranges
                    for current_range in rec.date_range_ids:
                        for other_range in other_profile.date_range_ids:
                            # Check if date ranges overlap
                            if (
                                current_range.date_start <= other_range.date_end
                                and current_range.date_end >= other_range.date_start
                            ):
                                raise ValidationError(
                                    self.env._(
                                        "Warehouse '{warehouse}' already has a profile '{other_profile}' "
                                        "with overlapping season '{other_season}' (from {start} to {end}). "
                                        "Current season '{current_season}' overlaps with it."
                                    ).format(
                                        warehouse=rec.warehouse_id.name,
                                        other_profile=other_profile.name,
                                        other_season=other_range.name,
                                        start=other_range.date_start,
                                        end=other_range.date_end,
                                        current_season=current_range.name,
                                    )
                                )

    def _generate_profile_name(self):
        """Generate profile name in format 'Warehouse | Zone | Season1 - Season2'."""
        self.ensure_one()
        if not self.warehouse_id or not self.date_range_ids:
            return ""

        warehouse_name = self.warehouse_id.name

        # Extract geographical zone from season names
        # Looking for patterns like "East valleys", "High central valleys", etc.
        zones = set()
        seasons = set()

        for date_range in self.date_range_ids:
            name_parts = date_range.name.split()
            # Extract zone (everything before the season words)
            zone_parts = []
            season_parts = []
            capturing_zone = True

            for part in name_parts:
                if part.lower() in ["spring", "summer", "autumn", "winter", "autum"]:
                    capturing_zone = False

                if capturing_zone and part.lower() not in [
                    "2018",
                    "2019",
                    "2020",
                    "2021",
                    "2022",
                    "2023",
                    "2024",
                    "2025",
                ]:
                    zone_parts.append(part)
                elif not capturing_zone and part.lower() in [
                    "spring",
                    "summer",
                    "autumn",
                    "winter",
                    "autum",
                ]:
                    season_parts.append(part.lower().replace("autum", "autumn"))

            if zone_parts:
                zones.add(" ".join(zone_parts))
            if season_parts:
                seasons.update(season_parts)

        # Build the name components
        zone_str = list(zones)[0] if zones else "Unknown zone"
        season_str = " - ".join(sorted(seasons)) if seasons else "Unknown season"

        return f"{warehouse_name} | {zone_str} | {season_str}"

    @api.onchange("warehouse_id", "date_range_ids", "interval_type")
    def _onchange_suggest_name(self):
        """Suggest profile name based on warehouse and seasons."""
        if self.profile_type == "sale_stock" and self.interval_type == "seasons":
            suggested_name = self._generate_profile_name()
            if suggested_name and not self.name:
                self.name = suggested_name

    @api.model
    def _get_collected_data_class(self):
        return SaleStockData

    def _init_collected_data_instance(self):
        self.ensure_one()
        sale_stock_data = self._get_collected_data_class()()
        sale_stock_data.profile = self
        return sale_stock_data

    def _get_all_product_ids(self):
        """Get a set of product ids with the current profile"""
        self.ensure_one()
        self.env.cr.execute(
            """
            SELECT
                abc_rel.product_id
            FROM
                abc_classification_profile_product_rel abc_rel
            JOIN
                product_product pp
                ON pp.id = abc_rel.product_id
            WHERE
                pp.active
                AND abc_rel.profile_id = %(profile_id)s
        """,
            {"profile_id": self.id},
        )
        return {r[0] for r in self.env.cr.fetchall()}

    def _get_sale_stock_data_query(self, from_date, to_date, customer_location_ids):
        """Get sale stock data query for specific date period.

        Args:
            from_date: Start date for the period
            to_date: End date for the period
            customer_location_ids: List of customer location IDs

        Returns:
            tuple: (query, params)
        """
        query = """
            SELECT
                sol.product_id product_id,
                COUNT(sol.id) number_so_lines
            FROM
                sale_order so
            JOIN
                sale_order_line sol ON
                sol.order_id = so.id
            JOIN
                abc_classification_profile_product_rel rel
                ON rel.product_id = sol.product_id
            JOIN
                product_product pp
                ON pp.id = sol.product_id
            WHERE sol.qty_transfered > 0
                AND pp.active
                AND rel.profile_id = %(profile_id)s
                AND so.warehouse_id = %(current_warehouse_id)s
                AND so.date_order >= %(from_date)s
                AND so.date_order <= %(to_date)s
            AND EXISTS (
                    SELECT
                        1
                    FROM
                        stock_move sm
                    WHERE
                        sm.location_dest_id in %(customer_loc_ids)s
                        AND sm.sale_line_id = sol.id
                )
            GROUP BY sol.product_id
            ORDER BY number_so_lines DESC
        """

        params = {
            "profile_id": self.id,
            "current_warehouse_id": self.warehouse_id.id,
            "customer_loc_ids": tuple(customer_location_ids),
            "from_date": from_date,
            "to_date": to_date,
        }

        return query, params

    def _get_date_periods(self):
        """Generate list of date periods based on profile configuration."""
        self.ensure_one()
        periods = []

        if self.interval_type == "seasons" and self.date_range_ids:
            # For seasonal profiles, create one period per active season
            for season in self.date_range_ids.filtered("active"):
                periods.append(
                    {
                        "from_date": season.date_start,
                        "to_date": season.date_end,
                        "season_id": season.id,
                    }
                )
        else:
            # For traditional profiles, single period based on days
            from_date = fields.Datetime.to_string(
                datetime.today() - timedelta(days=self.period)
            )
            to_date = datetime.today()
            periods.append(
                {
                    "from_date": from_date,
                    "to_date": to_date,
                    "season_id": None,
                }
            )

        return periods

    def _get_data(self, from_date, to_date, season_id=None):
        """Get a list of statics info from the DB ordered by number of lines desc

        Args:
            from_date: Start date for the period (required)
            to_date: End date for the period (required)
            season_id: Optional season ID for history tracking
        """
        self.ensure_one()

        customer_location_ids = (
            self.env["stock.location"].search([("usage", "=", "customer")]).ids
        )

        # Collect all the product linked to the profile to be sure to provide
        # information also for product no sold into the given period
        all_product_ids = self._get_all_product_ids()

        # Count the number of delivered order line by product linked to a
        # stock_move with a customer location as destination
        query, params = self._get_sale_stock_data_query(
            from_date, to_date, customer_location_ids
        )
        self.env.cr.execute(query, params)

        items = self.env.cr.fetchall()
        total = 0
        sale_stock_data_list = []
        ranking = 1
        product = self.env["product.product"]

        for item in items:
            sale_stock_data = self._init_collected_data_instance()
            product_id = item[0]
            sale_stock_data.product = product.browse(product_id)
            sale_stock_data.number_so_lines = int(item[1])
            sale_stock_data.ranking = ranking
            sale_stock_data.from_date = from_date
            sale_stock_data.to_date = to_date
            sale_stock_data.season_id = season_id
            ranking += 1
            total += int(item[1])
            sale_stock_data_list.append(sale_stock_data)
            all_product_ids.remove(product_id)

        # Add all products not sold or not delivered into this timelapse
        for product_id in all_product_ids:
            sale_stock_data = self._init_collected_data_instance()
            sale_stock_data.product = product.browse(product_id)
            sale_stock_data.number_so_lines = 0
            sale_stock_data.ranking = ranking
            sale_stock_data.from_date = from_date
            sale_stock_data.to_date = to_date
            sale_stock_data.season_id = season_id
            sale_stock_data_list.append(sale_stock_data)

        return sale_stock_data_list, total

    def _build_ordered_level_cumulative_percentage(self):
        """Return an ordered list of tuple of level, cumulative percentage

        The ordering is based on the level with the higher percentage first
        """
        self.ensure_one()
        levels = self.level_ids.sorted(key=attrgetter("percentage"), reverse=True)
        cum_percentages = []
        previous_percentage = None
        for i, level in enumerate(levels):
            perc = level.percentage + level.percentage_products
            if not i:
                percentage_to_append = perc
                cum_percentages.append(percentage_to_append)
            else:
                percentage_to_append = previous_percentage + perc
                cum_percentages.append(percentage_to_append)
            previous_percentage = percentage_to_append

        return list(zip(levels, cum_percentages))

    def _get_existing_level_ids(self):
        self.ensure_one()
        self.env.cr.execute(
            """
            SELECT
                id
            FROM
                abc_classification_product_level
            WHERE
                profile_id = %(profile_id)s
        """,
            {"profile_id": self.id},
        )
        return {r[0] for r in self.env.cr.fetchall()}

    def _purge_obsolete_level_values(self, ids_to_remove):
        if not ids_to_remove:
            return
        self.env.cr.execute(
            """
            DELETE FROM
                abc_classification_product_level
            WHERE
                id in %(ids)s
        """,
            {"ids": tuple(ids_to_remove)},
        )

    def _compute_abc_classification(self):
        to_compute = self.filtered(lambda p: p.profile_type == "sale_stock")
        remaining = self - to_compute
        res = None
        if remaining:
            res = super(
                AbcClassificationProfile, remaining
            )._compute_abc_classification()

        for profile in to_compute:
            # Generate date periods based on profile configuration
            date_periods = profile._get_date_periods()
            for period_info in date_periods:
                from_date = period_info["from_date"]
                to_date = period_info["to_date"]
                season_id = period_info.get("season_id")

                sale_stock_data_list, total = profile._get_data(
                    from_date, to_date, season_id
                )
                existing_level_ids_to_remove = profile._get_existing_level_ids()

                # Process ABC classification levels for the list of sale stock data
                level_percentage = profile._build_ordered_level_cumulative_percentage()
                if not level_percentage:
                    continue

                level, percentage = level_percentage.pop(0)
                previous_data = {}
                total_products = len(sale_stock_data_list)
                percentage_products = (
                    (100.0 / total_products) if total_products else 0.0
                )

                for i, sale_stock_data in enumerate(sale_stock_data_list):
                    computed_values = profile._process_abc_level(
                        sale_stock_data.number_so_lines,
                        i,
                        total,
                        total_products,
                        percentage_products,
                        previous_data,
                        level_percentage,
                        level,
                        percentage,
                    )

                    # Update sale_stock_data with computed values
                    sale_stock_data.total_products = computed_values["total_products"]
                    sale_stock_data.percentage_products = computed_values[
                        "percentage_products"
                    ]
                    sale_stock_data.cumulated_percentage_products = computed_values[
                        "cumulated_percentage_products"
                    ]
                    sale_stock_data.percentage = computed_values["percentage"]
                    sale_stock_data.cumulated_percentage = computed_values[
                        "cumulated_percentage"
                    ]
                    sale_stock_data.sum_cumulated_percentages = computed_values[
                        "sum_cumulated_percentages"
                    ]

                    # Update product classification
                    sale_stock_data.computed_level = computed_values["level"]
                    sale_stock_data.total_so_lines = total
                    product_abc_classification = (
                        profile._update_product_abc_classification(
                            sale_stock_data.product,
                            computed_values["level"],
                            existing_level_ids_to_remove,
                        )
                    )
                    sale_stock_data.product_level = product_abc_classification

                    level = computed_values["level"]
                    percentage = computed_values["level_percentage"]
                    previous_data = sale_stock_data

                if sale_stock_data_list:
                    profile._log_history(sale_stock_data_list)

                profile._purge_obsolete_level_values(existing_level_ids_to_remove)
        return res

    def _process_abc_level(
        self,
        number_so_lines,
        index,
        total,
        total_products,
        percentage_products,
        previous_data,
        level_percentage,
        current_level,
        current_percentage,
    ):
        """Process ABC classification calculations for a single product.

        Returns dict with computed values to be applied to sale_stock_data.
        """
        self.ensure_one()

        cumulated_percentage_products = (
            percentage_products
            if not index
            else (percentage_products + previous_data.cumulated_percentage_products)
        )

        # Compute percentages and cumulative percentages for the products
        percentage = (100.0 * number_so_lines / total) if total else 0.0

        cumulated_percentage = (
            percentage
            if not index
            else (percentage + previous_data.cumulated_percentage)
        )

        if float_round(cumulated_percentage, 0) > 100:
            raise UserError(self.env._("Cumulative percentage greater than 100."))

        sum_cumulated_percentages = cumulated_percentage + cumulated_percentage_products

        # Determine classification level
        current_level, current_percentage = self._determine_classification_level(
            sum_cumulated_percentages,
            level_percentage,
            current_level,
            current_percentage,
        )

        return {
            "total_products": total_products,
            "percentage_products": percentage_products,
            "cumulated_percentage_products": cumulated_percentage_products,
            "percentage": percentage,
            "cumulated_percentage": cumulated_percentage,
            "sum_cumulated_percentages": sum_cumulated_percentages,
            "level": current_level,
            "level_percentage": current_percentage,
        }

    def _update_product_abc_classification(
        self, product, current_level, existing_level_ids_to_remove
    ):
        """Update or create product ABC classification."""
        self.ensure_one()
        product_classification = self.env["abc.classification.product.level"]

        levels = product.abc_classification_product_level_ids
        product_abc_classification = levels.filtered(
            lambda p, prof=self: p.profile_id == prof
        )

        if product_abc_classification:
            # The line is still significant...
            existing_level_ids_to_remove.remove(product_abc_classification.id)
            if product_abc_classification.level_id != current_level:
                product_abc_classification.write(
                    {"computed_level_id": current_level.id}
                )
        else:
            product_abc_classification = product_classification.create(
                {
                    "computed_level_id": current_level.id,
                    "product_id": product.id,
                    "profile_id": self.id,
                }
            )

        return product_abc_classification

    def _determine_classification_level(
        self,
        sum_cumulated_percentages,
        level_percentage,
        current_level,
        current_percentage,
    ):
        """Determine the appropriate ABC classification level for a product."""
        # Compute ABC classification for the products based on the
        # sum of cumulated percentages
        if sum_cumulated_percentages > current_percentage and len(level_percentage) > 0:
            current_level, current_percentage = level_percentage.pop(0)

        return current_level, current_percentage

    def _log_history(self, sale_stock_data_list):
        """Log collected and computed values into
        abc.classification.product.level.history

        """
        if not sale_stock_data_list:
            return

        # Get period info from first item
        first_item = sale_stock_data_list[0]
        profile_id = first_item.profile.id
        from_date = first_item.from_date
        to_date = first_item.to_date
        season_id = first_item.season_id

        # Delete existing records for the same period before inserting new ones
        delete_query = """
            DELETE FROM abc_classification_product_level_history
            WHERE profile_id = %(profile_id)s
                AND from_date = %(from_date)s
                AND to_date = %(to_date)s
        """
        params = {
            "profile_id": profile_id,
            "from_date": from_date,
            "to_date": to_date,
        }

        # Include season_id in deletion if it's a seasonal profile
        if season_id:
            delete_query += " AND season_id = %(season_id)s"
            params["season_id"] = season_id

        self.env.cr.execute(delete_query, params)

        # Now insert the new records
        vals = StringIO()
        writer = csv.writer(vals, delimiter=";")
        for sale_stock_data in sale_stock_data_list:
            writer.writerow(sale_stock_data._to_csv_line())
        vals.seek(0)
        table = self.env["abc.classification.product.level.history"]._table
        columns = sale_stock_data_list[0]._get_col_names()
        self.env.cr.copy_from(vals, table, columns=columns, sep=";")

        # Force computation of seasonal analysis fields after bulk insert
        if season_id:
            # Get the inserted records for this period
            inserted_records = self.env[
                "abc.classification.product.level.history"
            ].search(
                [
                    ("profile_id", "=", profile_id),
                    ("from_date", "=", from_date),
                    ("to_date", "=", to_date),
                    ("season_id", "=", season_id),
                ]
            )
            # Trigger computation of seasonal fields
            inserted_records._compute_classification_variance()
            inserted_records._compute_season_performance()
            inserted_records._compute_strategic_segment()

        self.env["abc.classification.product.level"].invalidate_model(
            ["sale_stock_level_history_ids"]
        )


class SaleStockData:
    """Sale stock collected data

    This class is used to store all the data collectd and computed for
    a abc classification product level. It also provide methods used to bulk
    insert these data into the abc.classification.product.level.history table.

    """

    __slots__ = [
        "product",
        "profile",
        "computed_level",
        "ranking",
        "percentage",
        "cumulated_percentage",
        "number_so_lines",
        "total_so_lines",
        "product_level",
        "from_date",
        "to_date",
        "season_id",
        "total_products",
        "percentage_products",
        "cumulated_percentage_products",
        "sum_cumulated_percentages",
    ]

    def _to_csv_line(self):
        """Return values to write into a csv file"""
        return [
            self.product.id,
            self.product.product_tmpl_id.id,
            self.profile.id,
            self.computed_level.id,
            self.profile.warehouse_id.id,
            self.ranking,
            self.percentage,
            self.cumulated_percentage,
            self.number_so_lines,
            self.total_so_lines,
            self.product_level.id,
            self.from_date,
            self.to_date,
            self.season_id,
            self.total_products,
            self.percentage_products,
            self.cumulated_percentage_products,
            self.sum_cumulated_percentages,
        ]

    @classmethod
    def _get_col_names(cls):
        """Return the ordered list of column names related to the values
        returned by _to_csv_line

        We use the name of the columns defined into abc.classification.product.level.history
        """
        return [
            "product_id",
            "product_tmpl_id",
            "profile_id",
            "computed_level_id",
            "warehouse_id",
            "ranking",
            "percentage",
            "cumulated_percentage",
            "number_so_lines",
            "total_so_lines",
            "product_level_id",
            "from_date",
            "to_date",
            "season_id",
            "total_products",
            "percentage_products",
            "cumulated_percentage_products",
            "sum_cumulated_percentages",
        ]
