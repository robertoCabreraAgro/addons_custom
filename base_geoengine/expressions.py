# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import random
import string

from odoo import models
from odoo.osv import expression
from odoo.osv.expression import TERM_OPERATORS
from odoo.tools import SQL, Query

from .fields import GeoField

import logging

_logger = logging.getLogger(__name__)

# Definir los operadores geoespaciales
GEO_OPERATORS = {
    "geo_greater": ">",
    "geo_lesser": "<",
    "geo_equal": "=",
    "geo_touch": "ST_Touches",
    "geo_within": "ST_Within",
    "geo_contains": "ST_Contains",
    "geo_intersect": "ST_Intersects",
}

# Actualizar la lista de operadores de términos para incluir los operadores geoespaciales
expression.TERM_OPERATORS = tuple(list(TERM_OPERATORS) + list(GEO_OPERATORS.keys()))

# Guardar la referencia al método original _condition_to_sql
original_condition_to_sql = models.BaseModel._condition_to_sql


def _condition_to_sql(self, alias, field_name, operator, value, query):
    # _logger.info(
    #    "Iniciando _condition_to_sql con alias: %s, field_name: %s, operator: %s, value: %s",
    #    alias, field_name, operator, value
    # )

    if operator in GEO_OPERATORS:
        field = self._fields.get(field_name)
        if field and isinstance(field, GeoField):
            # _logger.info(
            #    "Operador geoespacial detectado: %s para campo geoespacial: %s",
            #    operator, field_name
            # )

            if isinstance(value, dict):
                ref_search = value
                sub_queries = []
                for key in ref_search:
                    # _logger.info("Procesando subconsulta para key: %s", key)
                    i = key.rfind(".")
                    rel_model_name = key[0:i]
                    rel_col = key[i + 1 :]
                    rel_model = self.env[rel_model_name]
                    # _logger.info("Relación: %s, Columna: %s", rel_model_name, rel_col)

                    if ref_search[key]:
                        rel_alias = (
                            rel_model._table
                            + "_"
                            + "".join(random.choices(string.ascii_lowercase, k=5))
                        )
                        # _logger.info("Alias generado para la relación: %s", rel_alias)

                        rel_query = where_calc(
                            rel_model,
                            ref_search[key],
                            active_test=True,
                            alias=rel_alias,
                        )
                        # _logger.info("Query de relación generada: %s", rel_query)

                        # rel_query.add_where(
                        #    rel_model._where_calc([])
                        # )
                        self._apply_ir_rules(rel_query, "read")
                        # _logger.info("Aplicadas reglas de acceso IR para la query")

                        # Construir la cláusula WHERE sin pasar objetos como parámetros
                        if operator == "geo_equal":
                            where_clause = '"{alias}"."{field_name}" {op} "{rel_alias}"."{rel_col}"'.format(
                                alias=alias,
                                field_name=field_name,
                                op=GEO_OPERATORS[operator],
                                rel_alias=rel_alias,
                                rel_col=rel_col,
                            )
                        elif operator in ("geo_greater", "geo_lesser"):
                            where_clause = 'ST_Area("{alias}"."{field_name}") {op} ST_Area("{rel_alias}"."{rel_col}")'.format(
                                alias=alias,
                                field_name=field_name,
                                op=GEO_OPERATORS[operator],
                                rel_alias=rel_alias,
                                rel_col=rel_col,
                            )
                        else:
                            where_clause = '{func}("{alias}"."{field_name}", "{rel_alias}"."{rel_col}")'.format(
                                func=GEO_OPERATORS[operator],
                                alias=alias,
                                field_name=field_name,
                                rel_alias=rel_alias,
                                rel_col=rel_col,
                            )
                        rel_query.add_where(where_clause)

                        # Obtener la cadena SQL y los parámetros de la subconsulta
                        subquery_sql, subquery_params = rel_query.select()

                        # Construir la cláusula EXISTS
                        exists_sql_code = "EXISTS(" + subquery_sql + ")"
                        exists_sql_params = subquery_params

                        # Crear el objeto SQL
                        exists_sql = SQL(exists_sql_code, *exists_sql_params)

                        # Agregar el objeto SQL a la lista de subconsultas
                        sub_queries.append(exists_sql)

                # Combinar las subconsultas con 'AND'
                if len(sub_queries) == 1:
                    query_result = sub_queries[0]
                else:
                    query_result = SQL(" AND ").join(sub_queries)
                # _logger.info("Resultado final de la consulta: %s", query_result)
                return query_result
            else:
                # Manejar el caso donde 'value' no es un diccionario
                query_result = get_geo_func(operator, alias, field_name, value)
                # _logger.info("Resultado de la función geoespacial: %s", query_result)
                return query_result
    else:
        # _logger.info("Operador no geoespacial: %s. Llamando al método original.", operator)
        return original_condition_to_sql(
            self, alias, field_name, operator, value, query
        )


def get_geo_func(operator, alias, field_name, value):
    """
    Este método llama a la consulta SQL correspondiente al operador geoespacial solicitado.
    """
    if operator in GEO_OPERATORS:
        func = GEO_OPERATORS[operator]
        # Convertir el objeto geométrico a WKT
        if hasattr(value, "wkt"):
            geom_wkt = value.wkt
        else:
            # Si 'value' no tiene atributo 'wkt', intentar convertirlo a cadena
            geom_wkt = str(value)
        # Construir la consulta SQL usando ST_GeomFromText
        query_str = '{func}("{alias}"."{field_name}", ST_GeomFromText(%s, {srid}))'.format(
            func=func,
            alias=alias,
            field_name=field_name,
            srid=3857,  # Reemplaza 'your_srid' con el SRID que estés utilizando, por ejemplo 4326
        )
        query = SQL(query_str, geom_wkt)
        return query
    else:
        raise NotImplementedError(f"El operador {operator} no está soportado")


from odoo.tools import SQL, Query


def where_calc(model, domain, active_test=True, alias=None):
    """
    Este método es una adaptación para crear nuestra propia consulta.
    """
    # Si el objeto tiene un campo activo ('active', 'x_active'), filtrar todos los registros inactivos
    if model._active_name and active_test and model._context.get("active_test", True):
        if not any(
            item[0] == model._active_name
            or (
                isinstance(item[0], str)
                and "." in item[0]
                and item[0].split(".", 1)[0] == model._active_name
            )
            for item in domain
            if isinstance(item, (list, tuple)) and len(item) > 0
        ):
            domain = [(model._active_name, "=", 1)] + domain

    # Asegurarnos de que 'alias' es una cadena
    if alias is None:
        alias = (
            model._table
        )  # Usar el nombre de la tabla como alias si no se proporciona uno

    # Convertir 'table' a un objeto SQL
    table = SQL.identifier(model._table)

    # Crear el objeto Query con los parámetros correctos
    query = Query(model.env, alias, table)

    if domain:
        expression_obj = expression.expression(domain, model, alias=alias, query=query)
        query = expression_obj.query
    return query


# Reemplazar el método _condition_to_sql en BaseModel
models.BaseModel._condition_to_sql = _condition_to_sql
