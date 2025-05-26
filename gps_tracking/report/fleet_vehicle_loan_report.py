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
    duration_hours = fields.Float(string="Duración (h)", readonly=True)

    def _query(self):
        return """
            SELECT
                ROW_NUMBER() OVER (ORDER BY start_p.timestamp) AS id,
                start_p.driver_name AS username,
                fv.name AS vehiculo,
                start_p.odometer AS odometer_start,
                end_p.odometer AS odometer_end,
                start_p.timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City' AS date_start,
                CASE EXTRACT(DOW FROM start_p.timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')
                    WHEN 0 THEN 'Domingo'
                    WHEN 1 THEN 'Lunes'
                    WHEN 2 THEN 'Martes'
                    WHEN 3 THEN 'Miércoles'
                    WHEN 4 THEN 'Jueves'
                    WHEN 5 THEN 'Viernes'
                    WHEN 6 THEN 'Sábado'
                END AS weekday_start,
                end_p.timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City' AS date_end,
                CASE EXTRACT(DOW FROM end_p.timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')
                    WHEN 0 THEN 'Domingo'
                    WHEN 1 THEN 'Lunes'
                    WHEN 2 THEN 'Martes'
                    WHEN 3 THEN 'Miércoles'
                    WHEN 4 THEN 'Jueves'
                    WHEN 5 THEN 'Viernes'
                    WHEN 6 THEN 'Sábado'
                END AS weekday_end,
                end_p.odometer - start_p.odometer AS distance,
                EXTRACT(EPOCH FROM (end_p.timestamp - start_p.timestamp)) / 3600.0 AS duration_hours
            FROM
                gps_tracking_point start_p
            JOIN
                gps_tracking_point end_p
                    ON end_p.device_id = start_p.device_id
                    AND end_p.driver_name = start_p.driver_name
                    AND start_p.is_week_start
                    AND end_p.is_week_end
                    AND DATE_TRUNC('week', start_p.timestamp) = DATE_TRUNC('week', end_p.timestamp)
            LEFT JOIN
                fleet_vehicle fv ON start_p.vehicle_id = fv.id
            ORDER BY
                start_p.timestamp DESC
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
