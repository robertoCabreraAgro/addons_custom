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

    def _get_date_ranges_for_query(self):
        """Get date ranges for query based on profile configuration"""
        self.ensure_one()
        if self.interval_type == "seasons" and self.date_range_ids:
            # Usar solo rangos de fecha activos
            active_ranges = self.date_range_ids.filtered("active")
            if not active_ranges:
                raise ValidationError(
                    self.env._(
                        "No active date ranges found for profile {profile_name}"
                    ).format(profile_name=self.name)
                )
            return active_ranges
        return self.env["date.range"]

    def _get_sale_stock_data_query(self, from_date, customer_location_ids):
        """Modified query to support date ranges"""
        date_ranges = self._get_date_ranges_for_query()

        if date_ranges:
            # Query con soporte para rangos de fecha específicos
            date_conditions = []
            for i, date_range in enumerate(date_ranges):
                date_conditions.append(
                    f"(so.date_order >= %(date_param_{i*2})s AND so.date_order <= %(date_param_{i*2+1})s)"
                )

            date_where_clause = " AND (" + " OR ".join(date_conditions) + ")"

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
                    {date_where_clause}
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
            """.format(
                date_where_clause=date_where_clause
            )

            params = {
                "profile_id": self.id,
                "current_warehouse_id": self.warehouse_id.id,
                "customer_loc_ids": tuple(customer_location_ids),
            }

            date_params = []
            for date_range in date_ranges:
                date_params.extend([date_range.date_start, date_range.date_end])

            return query, params, date_params

        else:
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
                AND EXISTS (
                        SELECT
                            1
                        FROM
                            stock_move sm
                        WHERE
                            sm.date > %(start_date)s
                            AND sm.location_dest_id in %(customer_loc_ids)s
                            AND sm.sale_line_id = sol.id
                    )
                GROUP BY sol.product_id
                ORDER BY number_so_lines DESC
            """
            params = {
                "start_date": from_date,
                "current_warehouse_id": self.warehouse_id.id,
                "profile_id": self.id,
                "customer_loc_ids": tuple(customer_location_ids),
            }
            return query, params, []

    def _get_data(self, from_date=None):
        """Get a list of statics info from the DB ordered by number of lines desc"""
        self.ensure_one()
        date_ranges = self._get_date_ranges_for_query()
        if date_ranges:
            from_date = min(date_ranges.mapped("date_start"))
            to_date = max(date_ranges.mapped("date_end"))
        else:
            from_date = (
                from_date
                if from_date
                else fields.Datetime.to_string(
                    datetime.today() - timedelta(days=self.period)
                )
            )
            to_date = datetime.today()

        customer_location_ids = (
            self.env["stock.location"].search([("usage", "=", "customer")]).ids
        )

        # Collect all the product linked to the profile to be sure to provide
        # information also for product no sold into the given period
        all_product_ids = self._get_all_product_ids()

        # Count the number of delivered order line by product linked to a
        # stock_move with a customer location as destination
        query_result = self._get_sale_stock_data_query(from_date, customer_location_ids)
        if len(query_result) == 3:
            query, params, date_params = query_result
            if date_params:
                # Merge date parameters into params dict
                for i, date_param in enumerate(date_params):
                    params[f"date_param_{i}"] = date_param
                self.env.cr.execute(query, params)
            else:
                self.env.cr.execute(query, params)
        else:
            query, params = query_result
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

    def _sale_stock_data_to_vals(self, sale_stock_data, create=False):
        self.ensure_one()
        res = {"computed_level_id": sale_stock_data.computed_level.id}
        if create:
            res.update(
                {
                    "product_id": sale_stock_data.product.id,
                    "profile_id": sale_stock_data.profile.id,
                }
            )
        return res

    def _compute_abc_classification(self):
        to_compute = self.filtered(lambda p: p.profile_type == "sale_stock")
        remaining = self - to_compute
        res = None
        if remaining:
            res = super(
                AbcClassificationProfile, remaining
            )._compute_abc_classification()
        product_classification = self.env["abc.classification.product.level"]
        for profile in to_compute:
            sale_stock_data_list, total = profile._get_data()
            existing_level_ids_to_remove = profile._get_existing_level_ids()
            level_percentage = profile._build_ordered_level_cumulative_percentage()
            if not level_percentage:
                continue
            level, percentage = level_percentage.pop(0)
            previous_data = {}
            total_products = len(sale_stock_data_list)
            percentage_products = (100.0 / total_products) if total_products else 0.0
            for i, sale_stock_data in enumerate(sale_stock_data_list):
                sale_stock_data.total_products = total_products
                sale_stock_data.percentage_products = percentage_products
                sale_stock_data.cumulated_percentage_products = (
                    sale_stock_data.percentage_products
                    if not i
                    else (
                        sale_stock_data.percentage_products
                        + previous_data.cumulated_percentage_products
                    )
                )
                # Compute percentages and cumulative percentages for the products
                sale_stock_data.percentage = (
                    (100.0 * sale_stock_data.number_so_lines / total) if total else 0.0
                )

                sale_stock_data.cumulated_percentage = (
                    sale_stock_data.percentage
                    if not i
                    else (
                        sale_stock_data.percentage + previous_data.cumulated_percentage
                    )
                )
                if float_round(sale_stock_data.cumulated_percentage, 0) > 100:
                    raise UserError(
                        self.env._("Cumulative percentage greater than 100.")
                    )

                sale_stock_data.sum_cumulated_percentages = (
                    sale_stock_data.cumulated_percentage
                    + sale_stock_data.cumulated_percentage_products
                )

                # Compute ABC classification for the products based on the
                # sum of cumulated percentages

                if (
                    sale_stock_data.sum_cumulated_percentages > percentage
                    and len(level_percentage) > 0
                ):
                    level, percentage = level_percentage.pop(0)

                product = sale_stock_data.product
                levels = product.abc_classification_product_level_ids
                product_abc_classification = levels.filtered(
                    lambda p, prof=profile: p.profile_id == prof
                )

                sale_stock_data.computed_level = level
                if product_abc_classification:
                    # The line is still significant...
                    existing_level_ids_to_remove.remove(product_abc_classification.id)
                    if product_abc_classification.level_id != level:
                        vals = profile._sale_stock_data_to_vals(
                            sale_stock_data, create=False
                        )
                        product_abc_classification.write(vals)
                else:
                    vals = profile._sale_stock_data_to_vals(
                        sale_stock_data, create=True
                    )
                    product_abc_classification = product_classification.create(vals)
                sale_stock_data.total_so_lines = total
                sale_stock_data.product_level = product_abc_classification
                previous_data = sale_stock_data
            if sale_stock_data_list:
                self._log_history(sale_stock_data_list)
            profile._purge_obsolete_level_values(existing_level_ids_to_remove)
        return res

    def _log_history(self, sale_stock_data_list):
        """Log collected and computed values into
        abc.sale_stock.level.history

        """
        vals = StringIO()
        writer = csv.writer(vals, delimiter=";")
        for sale_stock_data in sale_stock_data_list:
            writer.writerow(sale_stock_data._to_csv_line())
        vals.seek(0)
        table = self.env["abc.sale_stock.level.history"]._table
        columns = sale_stock_data_list[0]._get_col_names()
        self.env.cr.copy_from(vals, table, columns=columns, sep=";")
        self.env["abc.classification.product.level"].invalidate_model(
            ["sale_stock_level_history_ids"]
        )


class SaleStockData:
    """Sale stock collected data

    This class is used to store all the data collectd and computed for
    a abc classification product level. It also provide methods used to bulk
    insert these data into the abc.sale_stock.level.history table.

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
            self.total_products,
            self.percentage_products,
            self.cumulated_percentage_products,
            self.sum_cumulated_percentages,
        ]

    @classmethod
    def _get_col_names(cls):
        """Return the ordered list of column names related to the values
        returned by _to_csv_line

        We use the name of the columns defined into abc.sale_stock.level.history
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
            "total_products",
            "percentage_products",
            "cumulated_percentage_products",
            "sum_cumulated_percentages",
        ]
