from odoo import http
from odoo.http import request
import json


class EstateController(http.Controller):

    @http.route('/estate/get_properties', type='json', auth='user')
    def get_properties(self, **kwargs):
        """Obtiene las propiedades de bienes raíces"""
        try:
            properties = request.env['estate.property'].search_read(
                domain=[],
                fields=['id', 'name', 'description', 'postcode', 'expected_price', 
                       'selling_price', 'bedrooms', 'living_area', 'state', 
                       'property_type_id', 'date_availability'],
                limit=100
            )
            return {
                'status': 'success',
                'data': properties
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/estate/get_offers', type='json', auth='user')
    def get_offers(self, **kwargs):
        """Obtiene las ofertas de propiedades"""
        try:
            offers = request.env['estate.property.offer'].search_read(
                domain=[],
                fields=['id', 'price', 'status', 'partner_id', 'property_id',
                       'validity', 'date_deadline'],
                limit=100
            )
            return {
                'status': 'success',
                'data': offers
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/estate/get_property_types', type='json', auth='user')
    def get_property_types(self, **kwargs):
        """Obtiene los tipos de propiedades"""
        try:
            property_types = request.env['estate.property.type'].search_read(
                domain=[],
                fields=['id', 'name', 'sequence'],
                order='sequence'
            )
            return {
                'status': 'success',
                'data': property_types
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
            
    @http.route('/estate/get_dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, **kwargs):
        """Obtiene datos para el dashboard y gráficos"""
        try:
            # Estadísticas de propiedades por estado
            properties_by_state_query = """
                SELECT 
                    CASE 
                        WHEN state = 'new' THEN 'Nuevas'
                        WHEN state = 'offer_received' THEN 'Con Ofertas'
                        WHEN state = 'offer_accepted' THEN 'Oferta Aceptada'
                        WHEN state = 'sold' THEN 'Vendidas'
                        WHEN state = 'canceled' THEN 'Canceladas'
                        ELSE 'Otro'
                    END as state_name,
                    COUNT(*) as property_count
                FROM estate_property
                WHERE active = true
                GROUP BY state
                ORDER BY property_count DESC
            """
            request.env.cr.execute(properties_by_state_query)
            properties_by_state = request.env.cr.dictfetchall()

            # Propiedades por tipo
            properties_by_type_query = """
                SELECT 
                    COALESCE(ept.name, 'Sin Tipo') as type_name,
                    COUNT(ep.id) as property_count,
                    AVG(ep.expected_price) as avg_price
                FROM estate_property ep
                LEFT JOIN estate_property_type ept ON ep.property_type_id = ept.id
                WHERE ep.active = true
                GROUP BY ept.id, ept.name
                ORDER BY property_count DESC
                LIMIT 10
            """
            request.env.cr.execute(properties_by_type_query)
            properties_by_type = request.env.cr.dictfetchall()

            # Rangos de precios
            price_ranges_query = """
                SELECT 
                    CASE 
                        WHEN expected_price <= 100000 THEN 'Hasta $100K'
                        WHEN expected_price <= 300000 THEN '$100K-$300K'
                        WHEN expected_price <= 500000 THEN '$300K-$500K'
                        WHEN expected_price <= 800000 THEN '$500K-$800K'
                        ELSE 'Más de $800K'
                    END as price_range,
                    COUNT(*) as property_count
                FROM estate_property
                WHERE active = true AND expected_price > 0
                GROUP BY 
                    CASE 
                        WHEN expected_price <= 100000 THEN 'Hasta $100K'
                        WHEN expected_price <= 300000 THEN '$100K-$300K'
                        WHEN expected_price <= 500000 THEN '$300K-$500K'
                        WHEN expected_price <= 800000 THEN '$500K-$800K'
                        ELSE 'Más de $800K'
                    END
                ORDER BY 
                    MIN(CASE 
                        WHEN expected_price <= 100000 THEN 1
                        WHEN expected_price <= 300000 THEN 2
                        WHEN expected_price <= 500000 THEN 3
                        WHEN expected_price <= 800000 THEN 4
                        ELSE 5
                    END)
            """
            request.env.cr.execute(price_ranges_query)
            price_ranges = request.env.cr.dictfetchall()

            # Ofertas por estado
            offers_by_status_query = """
                SELECT 
                    CASE 
                        WHEN status = 'accepted' THEN 'Aceptadas'
                        WHEN status = 'refused' THEN 'Rechazadas'
                        ELSE 'Pendientes'
                    END as status_name,
                    COUNT(*) as offer_count,
                    AVG(price) as avg_offer_price
                FROM estate_property_offer
                GROUP BY status
            """
            request.env.cr.execute(offers_by_status_query)
            offers_by_status = request.env.cr.dictfetchall()

            return {
                'status': 'success',
                'data': {
                    'properties_by_state': properties_by_state,
                    'properties_by_type': properties_by_type,
                    'price_ranges': price_ranges,
                    'offers_by_status': offers_by_status
                }
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
