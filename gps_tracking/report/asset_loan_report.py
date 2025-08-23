from odoo import fields, models, tools
import logging

_logger = logging.getLogger(__name__)


class AssetLoanReport(models.Model):
    _name = "asset.loan.report"
    _description = "Reporte de préstamos de vehículos"
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
    work_hours_status = fields.Char(string="Estatus laboral", readonly=True)

    def _query(self):
        return """
        WITH
        -- Step 1: Define trip segments.
            TripSegments AS (
                SELECT
                    a.employee_id,
                    a.check_in AS start_time,
                    a.check_out AS end_time,
                    'Dentro del trabajo' AS work_hours_status
                FROM
                    hr_attendance AS a
                JOIN
                    hr_employee AS he
                    ON a.employee_id = he.id
                WHERE
                    a.check_out IS NOT NULL
                    AND he.enable_vehicle_loan = TRUE
                UNION ALL
                SELECT
                    a.employee_id,
                    a.check_out AS start_time,
                    LEAD(a.check_in) OVER (
                        PARTITION BY a.employee_id
                        ORDER BY a.check_in
                    ) AS end_time,
                    'Fuera del trabajo' AS work_hours_status
                FROM
                    hr_attendance AS a
                JOIN
                    hr_employee AS he
                    ON a.employee_id = he.id
                WHERE
                    he.enable_vehicle_loan = TRUE
            ),
        -- Step 2: For each trip segment, find the ID of the nearest start and end GPS point.
            TripDataPoints AS (
                SELECT
                    ts.employee_id,
                    ts.start_time,
                    ts.end_time,
                    ts.work_hours_status,
                    he.name AS username,
                -- Find the single closest GPS point ID at the START of the trip
                    (
                        SELECT
                            gtp.id
                        FROM
                            gps_tracking_point AS gtp
                        WHERE
                            gtp.driver_id = ts.employee_id
                            AND gtp."timestamp" BETWEEN
                                (ts.start_time - interval '2 hours')
                                AND (ts.start_time + interval '2 hours')
                        ORDER BY
                            ABS(EXTRACT(EPOCH FROM (gtp."timestamp" - ts.start_time)))
                        LIMIT 1
                    ) AS start_point_id
                FROM
                    TripSegments AS ts
                JOIN
                    hr_employee AS he
                    ON ts.employee_id = he.id
                WHERE
                    ts.end_time IS NOT NULL
            ),
        -- Step 3: Get start point details and find matching end point for the same vehicle
            TripDataWithVehicle AS (
                SELECT
                    tdp.*,
                    start_point.id AS start_point_id_final,
                    start_point.device_id AS device_id,
                    -- Find the closest GPS point at the END of the trip for the SAME DEVICE/VEHICLE
                    (
                        SELECT
                            gtp.id
                        FROM
                            gps_tracking_point AS gtp
                        WHERE
                            gtp.device_id = start_point.device_id  -- Same device as start point
                            AND gtp."timestamp" BETWEEN
                                (tdp.end_time - interval '2 hours')
                                AND (tdp.end_time + interval '2 hours')
                        ORDER BY
                            ABS(EXTRACT(EPOCH FROM (gtp."timestamp" - tdp.end_time)))
                        LIMIT 1
                    ) AS end_point_id
                FROM
                    TripDataPoints AS tdp
                LEFT JOIN
                    gps_tracking_point AS start_point
                    ON tdp.start_point_id = start_point.id
            )
        -- Step 4: Final report - join the point IDs to get all details.
        SELECT
            (row_number() OVER ())::integer AS id,
            tdv.username,
            sl.name AS vehiculo,
            tdv.work_hours_status,
            start_point.real_odometer AS odometer_start,
            end_point.real_odometer AS odometer_end,
            tdv.start_time AS date_start,
            CASE EXTRACT(DOW FROM tdv.start_time AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')
                WHEN 0 THEN 'Domingo'
                WHEN 1 THEN 'Lunes'
                WHEN 2 THEN 'Martes'
                WHEN 3 THEN 'Miércoles'
                WHEN 4 THEN 'Jueves'
                WHEN 5 THEN 'Viernes'
                WHEN 6 THEN 'Sábado'
            END AS weekday_start,
            tdv.end_time AS date_end,
            CASE EXTRACT(DOW FROM tdv.end_time AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')
                WHEN 0 THEN 'Domingo'
                WHEN 1 THEN 'Lunes'
                WHEN 2 THEN 'Martes'
                WHEN 3 THEN 'Miércoles'
                WHEN 4 THEN 'Jueves'
                WHEN 5 THEN 'Viernes'
                WHEN 6 THEN 'Sábado'
            END AS weekday_end,
            CASE
                WHEN end_point.real_odometer - start_point.real_odometer < 0 THEN 0
                ELSE COALESCE(end_point.real_odometer - start_point.real_odometer, 0)
            END AS distance
        FROM
            TripDataWithVehicle AS tdv
        LEFT JOIN
            gps_tracking_point AS start_point
            ON tdv.start_point_id_final = start_point.id
        LEFT JOIN
            gps_tracking_point AS end_point
            ON tdv.end_point_id = end_point.id
        LEFT JOIN
            gps_tracking_device AS gtd
            ON tdv.device_id = gtd.id
        LEFT JOIN
            stock_lot AS sl
            ON gtd.asset_id = sl.id
        WHERE
            tdv.start_point_id IS NOT NULL
        ORDER BY
            tdv.start_time
        """

    def refresh_data(self):
        """Method called by the UI action to refresh the report data"""
        _logger.info("Refreshing report data for asset_loan_report")
        try:
            self.env.cr.execute("DROP VIEW IF EXISTS asset_loan_report")
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
