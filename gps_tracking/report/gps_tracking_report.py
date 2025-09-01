from datetime import timedelta

from odoo import fields, models, tools


class GpsTrackingReport(models.Model):
    _name = "gps.tracking.report"
    _description = "GPS Tracking Report"
    _auto = False
    _order = "date desc"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    device_id = fields.Many2one("gps.tracking.device", string="Device")
    imei = fields.Char(string="IMEI", readonly=True)
    asset_id = fields.Many2one("stock.lot", string="Asset", readonly=True)
    date = fields.Date(string="Date", readonly=True)
    avg_speed = fields.Float(string="Average Speed")
    max_speed = fields.Float(string="Maximum Speed")
    total_distance = fields.Float(string="Total Distance")
    fuel_consumed = fields.Float(string="Fuel Consumed")
    engine_hours = fields.Float(string="Engine Hours")

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER() AS id,
                    DATE(p.timestamp) AS date,
                    p.device_id,
                    d.imei AS imei,
                    d.asset_id AS asset_id,
                    AVG(p.speed) AS avg_speed,
                    MAX(p.speed) AS max_speed,
                    MAX(p.odometer) - MIN(p.odometer) AS total_distance,
                    MAX(p.fuel_consumed_counted) - MIN(p.fuel_consumed_counted) AS fuel_consumed,
                    MAX(p.engine_total_hours) - MIN(p.engine_total_hours) AS engine_hours
                FROM
                    gps_tracking_point p
                JOIN
                    gps_tracking_device d ON p.device_id = d.id
                GROUP BY
                    DATE(p.timestamp), p.device_id, d.imei, d.asset_id
            )
            """
            % (self._table,)
        )

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_view_tracking_point_ids(self):
        """
        Botón de acción para ver los puntos de rastreo detallados de este segmento
        """
        self.ensure_one()
        start_date = self.date
        end_date = self.date + timedelta(days=1)

        return {
            "name": "Tracking Points for {} on {}".format(
                self.asset_id.name, self.date
            ),
            "type": "ir.actions.act_window",
            "res_model": "gps.tracking.point",
            "view_mode": "list,form",
            "domain": [
                ("device_id", "=", self.device_id.id),
                ("timestamp", ">=", start_date),
                ("timestamp", "<", end_date),
            ],
            "context": {"create": False, "edit": False},
            "target": "current",
        }
