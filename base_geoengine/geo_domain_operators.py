from odoo.orm.domains import operator_optimization, Domain
from odoo.tools import SQL
from .geo_operators import GeoOperator
from . import fields as geo_fields

# Define geo operators
GEO_OPERATORS = [
    "geo_greater",
    "geo_lesser",
    "geo_equal",
    "geo_touch",
    "geo_within",
    "geo_contains",
    "geo_intersect",
]


@operator_optimization(GEO_OPERATORS)
def _optimize_geo_operators(condition, model):
    """Handle geospatial operators using modern Odoo operator optimization"""
    field = condition._field()

    # Only handle geo fields
    if not isinstance(field, geo_fields.GeoField):
        return condition

    operator = condition.operator
    value = condition.value
    field_expr = condition.field_expr

    geo_operator = GeoOperator(field)
    table = model._table
    params = []

    # Handle the different geo operators
    if operator == "geo_greater":
        sql_query = geo_operator.get_geo_greater_sql(table, field_expr, value, params)
    elif operator == "geo_lesser":
        sql_query = geo_operator.get_geo_lesser_sql(table, field_expr, value, params)
    elif operator == "geo_equal":
        sql_query = geo_operator.get_geo_equal_sql(table, field_expr, value, params)
    elif operator == "geo_touch":
        sql_query = geo_operator.get_geo_touch_sql(table, field_expr, value, params)
    elif operator == "geo_within":
        sql_query = geo_operator.get_geo_within_sql(table, field_expr, value, params)
    elif operator == "geo_contains":
        sql_query = geo_operator.get_geo_contains_sql(table, field_expr, value, params)
    elif operator == "geo_intersect":
        sql_query = geo_operator.get_geo_intersect_sql(table, field_expr, value, params)
    else:
        return condition

    # Return SQL condition wrapped in appropriate domain structure
    return Domain(SQL(sql_query, *params))
