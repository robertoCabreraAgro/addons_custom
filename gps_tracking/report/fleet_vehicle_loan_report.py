from odoo import fields, models, tools
import logging

_logger = logging.getLogger(__name__)


class FleetVehicleLoanReport(models.Model):
    _name = "fleet.vehicle.loan.report"
    _description = "Reporte de préstamos de vehículos aprobados"
    _auto = False
    _order = "date_start desc"

    username = fields.Char(string="Solicitante", readonly=True)
    vehiculo = fields.Char(string="Vehículo", readonly=True)
    odometer_start = fields.Float(string="Odómetro inicial", readonly=True)
    odometer_end = fields.Float(string="Odómetro final", readonly=True)
    date_start = fields.Datetime(string="Fecha inicio", readonly=True)
    weekday_start = fields.Char(string="Día inicio", readonly=True)
    date_end = fields.Datetime(string="Fecha fin", readonly=True)
    weekday_end = fields.Char(string="Día fin", readonly=True)
    distance = fields.Float(string="Distancia Recorrida", readonly=True)
    date = fields.Datetime(string="Fecha de Aprobación", readonly=True)

    def _query(self):
        return """
            SELECT 
            ar.id,
            rp.name AS username,
            fv.name AS vehiculo,
            ar.odometer AS odometer_start,
            ar.date AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City' AS date,
            LEAD(ar.odometer) OVER (
                PARTITION BY ar.vehicle_id, ar.request_owner_id 
                ORDER BY ar.date_start
            ) AS odometer_end,
            ar.date_start AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City' AS date_start,
            CASE EXTRACT(DOW FROM ar.date_start AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')
                WHEN 0 THEN 'Domingo' 
                WHEN 1 THEN 'Lunes' 
                WHEN 2 THEN 'Martes' 
                WHEN 3 THEN 'Miércoles' 
                WHEN 4 THEN 'Jueves' 
                WHEN 5 THEN 'Viernes' 
                WHEN 6 THEN 'Sábado' 
            END AS weekday_start,
            ar.date_end AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City' AS date_end,
            CASE EXTRACT(DOW FROM ar.date_end AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')
                WHEN 0 THEN 'Domingo' 
                WHEN 1 THEN 'Lunes' 
                WHEN 2 THEN 'Martes' 
                WHEN 3 THEN 'Miércoles' 
                WHEN 4 THEN 'Jueves' 
                WHEN 5 THEN 'Viernes' 
                WHEN 6 THEN 'Sábado' 
            END AS weekday_end,
            COALESCE(
                LEAD(ar.odometer) OVER (
                    PARTITION BY ar.vehicle_id, ar.request_owner_id 
                    ORDER BY ar.date_start
                ) - ar.odometer, 
                0
            ) AS distance
        FROM 
            approval_request ar
        JOIN 
            res_users ru ON ar.request_owner_id = ru.id
        JOIN 
            res_partner rp ON ru.partner_id = rp.id
        LEFT JOIN 
            fleet_vehicle fv ON ar.vehicle_id = fv.id
        WHERE 
            ar.category_id = 108
            AND ar.request_status = 'approved'
        ORDER BY 
            ar.date_start DESC
        """

    def refresh_data(self):
        """Method called by the UI action to refresh the report data"""
        _logger.info("Refreshing report data for fleet_vehicle_loan_report")
        try:
            self.env.cr.execute("DROP VIEW IF EXISTS fleet_vehicle_loan_report")
            self.init()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Éxito",
                    "message": "El reporte se ha actualizado correctamente",
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as e:
            _logger.error(f"Error refreshing report data: {e}")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": f"Error al actualizar el reporte: {e}",
                    "type": "danger",
                    "sticky": True,
                },
            }

    def init(self):
        """Initialize the SQL view"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                {self._query()}
            )
        """
        )
