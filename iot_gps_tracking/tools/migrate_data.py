#!/usr/bin/env python3
"""
Data Migration Tool for IoT GPS Tracking
Migrate GPS data from legacy systems or between Odoo versions
"""

import json
import csv
import psycopg2
import argparse
from datetime import datetime
import os
import sys


class DataMigrator:
    """Migrate GPS tracking data between systems"""

    def __init__(
        self,
        source_db,
        dest_db,
        source_user="odoo",
        source_password="odoo",
        dest_user="odoo",
        dest_password="odoo",
        source_host="localhost",
        dest_host="localhost",
    ):
        self.source_db = source_db
        self.dest_db = dest_db
        self.source_user = source_user
        self.source_password = source_password
        self.dest_user = dest_user
        self.dest_password = dest_password
        self.source_host = source_host
        self.dest_host = dest_host
        self.mapping = {}
        self.stats = {
            "devices": 0,
            "points": 0,
            "geofences": 0,
            "configs": 0,
            "errors": [],
        }

    def connect_source(self):
        """Connect to source database"""
        return psycopg2.connect(
            dbname=self.source_db,
            user=self.source_user,
            password=self.source_password,
            host=self.source_host,
        )

    def connect_dest(self):
        """Connect to destination database"""
        return psycopg2.connect(
            dbname=self.dest_db,
            user=self.dest_user,
            password=self.dest_password,
            host=self.dest_host,
        )

    def migrate_from_legacy_gps_tracking(self):
        """Migrate from legacy gps_tracking module to iot_gps_tracking"""
        print("🔄 Migrating from legacy gps_tracking module...")

        source_conn = self.connect_source()
        dest_conn = self.connect_dest()

        try:
            # Migrate devices
            print("\n📱 Migrating GPS devices...")
            self._migrate_legacy_devices(source_conn, dest_conn)

            # Migrate tracking points
            print("\n📍 Migrating tracking points...")
            self._migrate_legacy_points(source_conn, dest_conn)

            # Migrate geofences if they exist
            print("\n🗺️ Migrating geofences...")
            self._migrate_legacy_geofences(source_conn, dest_conn)

            # Commit changes
            dest_conn.commit()

            print("\n✅ Migration completed successfully!")
            self._print_stats()

        except Exception as e:
            dest_conn.rollback()
            print(f"\n❌ Migration failed: {e}")
            self.stats["errors"].append(str(e))

        finally:
            source_conn.close()
            dest_conn.close()

    def _migrate_legacy_devices(self, source_conn, dest_conn):
        """Migrate devices from legacy module"""
        source_cur = source_conn.cursor()
        dest_cur = dest_conn.cursor()

        # Check if legacy table exists
        source_cur.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'gps_device'
            )
        """
        )

        if not source_cur.fetchone()[0]:
            print("  ⚠️ No legacy gps_device table found")
            return

        # Get legacy devices
        source_cur.execute(
            """
            SELECT 
                id, name, imei, active, company_id,
                last_latitude, last_longitude, last_update,
                create_uid, create_date, write_uid, write_date
            FROM gps_device
            ORDER BY id
        """
        )

        devices = source_cur.fetchall()

        # Get or create GPS virtual box
        dest_cur.execute(
            """
            SELECT id FROM iot_box 
            WHERE identifier = 'gps_virtual_box'
            LIMIT 1
        """
        )

        box_result = dest_cur.fetchone()
        if box_result:
            box_id = box_result[0]
        else:
            dest_cur.execute(
                """
                INSERT INTO iot_box (name, identifier, ip, version, create_uid, write_uid, create_date, write_date)
                VALUES ('GPS Virtual Box', 'gps_virtual_box', 'virtual.gps.local', '1.0', 1, 1, NOW(), NOW())
                RETURNING id
            """
            )
            box_id = dest_cur.fetchone()[0]

        # Migrate each device
        for device in devices:
            old_id, name, imei, active, company_id, lat, lon, last_update = device[:8]
            create_uid, create_date, write_uid, write_date = device[8:]

            # Check if device already exists
            dest_cur.execute(
                """
                SELECT id FROM iot_device 
                WHERE gps_imei = %s
                LIMIT 1
            """,
                (imei,),
            )

            existing = dest_cur.fetchone()

            if not existing:
                # Insert new device
                dest_cur.execute(
                    """
                    INSERT INTO iot_device (
                        name, identifier, type, iot_id, connection,
                        gps_imei, gps_tracking_enabled, gps_last_latitude,
                        gps_last_longitude, gps_last_update, company_id,
                        create_uid, create_date, write_uid, write_date
                    ) VALUES (
                        %s, %s, 'gps_tracker', %s, 'network',
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    ) RETURNING id
                """,
                    (
                        name,
                        f"gps_{imei}",
                        box_id,
                        imei,
                        active,
                        lat,
                        lon,
                        last_update,
                        company_id,
                        create_uid,
                        create_date,
                        write_uid,
                        write_date,
                    ),
                )

                new_id = dest_cur.fetchone()[0]
                self.mapping[f"device_{old_id}"] = new_id
                self.stats["devices"] += 1
                print(f"  ✅ Migrated device: {name} (IMEI: {imei})")
            else:
                self.mapping[f"device_{old_id}"] = existing[0]
                print(f"  ℹ️ Device already exists: {name} (IMEI: {imei})")

    def _migrate_legacy_points(self, source_conn, dest_conn):
        """Migrate tracking points from legacy module"""
        source_cur = source_conn.cursor()
        dest_cur = dest_conn.cursor()

        # Check if legacy table exists
        source_cur.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'gps_tracking_point'
            )
        """
        )

        if not source_cur.fetchone()[0]:
            print("  ⚠️ No legacy gps_tracking_point table found")
            return

        # Get count of points to migrate
        source_cur.execute("SELECT COUNT(*) FROM gps_tracking_point")
        total_points = source_cur.fetchone()[0]

        print(f"  📍 Found {total_points} tracking points to migrate")

        # Migrate in batches
        batch_size = 1000
        offset = 0

        while offset < total_points:
            source_cur.execute(
                """
                SELECT 
                    device_id, timestamp, latitude, longitude,
                    altitude, speed, satellites, accuracy, heading,
                    battery_level, ignition_state, movement_state,
                    odometer, fuel_level, engine_temp, engine_rpm,
                    create_uid, create_date, write_uid, write_date
                FROM gps_tracking_point
                ORDER BY id
                LIMIT %s OFFSET %s
            """,
                (batch_size, offset),
            )

            points = source_cur.fetchall()

            for point in points:
                device_id = point[0]
                new_device_id = self.mapping.get(f"device_{device_id}")

                if new_device_id:
                    # Insert tracking point
                    dest_cur.execute(
                        """
                        INSERT INTO iot_gps_tracking_point (
                            iot_device_id, timestamp, latitude, longitude,
                            altitude, speed, satellites, accuracy, heading,
                            battery_level, ignition, movement,
                            odometer, fuel_level, engine_temp, engine_rpm,
                            create_uid, create_date, write_uid, write_date
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                    """,
                        (new_device_id,) + point[1:],
                    )

                    self.stats["points"] += 1

            offset += batch_size
            print(f"  ✅ Migrated {min(offset, total_points)}/{total_points} points")

    def _migrate_legacy_geofences(self, source_conn, dest_conn):
        """Migrate geofences from legacy module"""
        source_cur = source_conn.cursor()
        dest_cur = dest_conn.cursor()

        # Check if legacy table exists
        source_cur.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'gps_geofence'
            )
        """
        )

        if not source_cur.fetchone()[0]:
            print("  ⚠️ No legacy gps_geofence table found")
            return

        # Get legacy geofences
        source_cur.execute(
            """
            SELECT 
                name, type, coordinates, radius, active,
                alert_on_enter, alert_on_exit, company_id,
                create_uid, create_date, write_uid, write_date
            FROM gps_geofence
            ORDER BY id
        """
        )

        geofences = source_cur.fetchall()

        for fence in geofences:
            name, fence_type, coords, radius, active = fence[:5]
            alert_enter, alert_exit, company_id = fence[5:8]
            create_uid, create_date, write_uid, write_date = fence[8:]

            # Parse coordinates based on type
            if fence_type == "circle":
                # Extract center lat/lon from coordinates
                center = json.loads(coords) if coords else {}
                center_lat = center.get("lat", 0)
                center_lon = center.get("lon", 0)
            else:
                center_lat = center_lon = 0
                radius = 0

            # Insert geofence
            dest_cur.execute(
                """
                INSERT INTO iot_gps_geofence (
                    name, type, center_latitude, center_longitude,
                    radius, polygon_points, active,
                    alert_on_enter, alert_on_exit, company_id,
                    create_uid, create_date, write_uid, write_date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                ) RETURNING id
            """,
                (
                    name,
                    fence_type,
                    center_lat,
                    center_lon,
                    radius,
                    coords if fence_type != "circle" else None,
                    active,
                    alert_enter,
                    alert_exit,
                    company_id,
                    create_uid,
                    create_date,
                    write_uid,
                    write_date,
                ),
            )

            self.stats["geofences"] += 1
            print(f"  ✅ Migrated geofence: {name}")

    def export_to_csv(self, output_dir="gps_export"):
        """Export GPS data to CSV files for backup or analysis"""
        print(f"📤 Exporting GPS data to {output_dir}/...")

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        conn = self.connect_source()

        try:
            # Export devices
            self._export_devices_csv(conn, output_dir)

            # Export tracking points
            self._export_points_csv(conn, output_dir)

            # Export geofences
            self._export_geofences_csv(conn, output_dir)

            print(f"\n✅ Export completed to {output_dir}/")

        except Exception as e:
            print(f"\n❌ Export failed: {e}")

        finally:
            conn.close()

    def _export_devices_csv(self, conn, output_dir):
        """Export devices to CSV"""
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 
                id, name, identifier, type, gps_imei,
                gps_last_latitude, gps_last_longitude,
                gps_last_update, gps_tracking_enabled,
                company_id
            FROM iot_device
            WHERE type = 'gps_tracker'
            ORDER BY id
        """
        )

        with open(f"{output_dir}/devices.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "name",
                    "identifier",
                    "type",
                    "imei",
                    "last_latitude",
                    "last_longitude",
                    "last_update",
                    "tracking_enabled",
                    "company_id",
                ]
            )
            writer.writerows(cursor.fetchall())

        print(f"  ✅ Exported devices to {output_dir}/devices.csv")

    def _export_points_csv(self, conn, output_dir):
        """Export tracking points to CSV"""
        cursor = conn.cursor()

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM iot_gps_tracking_point")
        total = cursor.fetchone()[0]

        print(f"  📍 Exporting {total} tracking points...")

        # Export in chunks to avoid memory issues
        chunk_size = 10000
        file_num = 1
        offset = 0

        while offset < total:
            cursor.execute(
                """
                SELECT 
                    iot_device_id, timestamp, latitude, longitude,
                    altitude, speed, satellites, accuracy, heading,
                    battery_level, ignition, movement,
                    odometer, fuel_level
                FROM iot_gps_tracking_point
                ORDER BY timestamp
                LIMIT %s OFFSET %s
            """,
                (chunk_size, offset),
            )

            rows = cursor.fetchall()

            filename = f"{output_dir}/tracking_points_{file_num:03d}.csv"
            with open(filename, "w", newline="") as f:
                writer = csv.writer(f)
                if file_num == 1:
                    writer.writerow(
                        [
                            "device_id",
                            "timestamp",
                            "latitude",
                            "longitude",
                            "altitude",
                            "speed",
                            "satellites",
                            "accuracy",
                            "heading",
                            "battery_level",
                            "ignition",
                            "movement",
                            "odometer",
                            "fuel_level",
                        ]
                    )
                writer.writerows(rows)

            print(f"  ✅ Exported {filename}")

            offset += chunk_size
            file_num += 1

    def _export_geofences_csv(self, conn, output_dir):
        """Export geofences to CSV"""
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 
                id, name, type, center_latitude, center_longitude,
                radius, active, alert_on_enter, alert_on_exit,
                company_id
            FROM iot_gps_geofence
            ORDER BY id
        """
        )

        with open(f"{output_dir}/geofences.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "name",
                    "type",
                    "center_lat",
                    "center_lon",
                    "radius",
                    "active",
                    "alert_enter",
                    "alert_exit",
                    "company_id",
                ]
            )
            writer.writerows(cursor.fetchall())

        print(f"  ✅ Exported geofences to {output_dir}/geofences.csv")

    def _print_stats(self):
        """Print migration statistics"""
        print("\n📊 Migration Statistics:")
        print(f"  • Devices migrated: {self.stats['devices']}")
        print(f"  • Tracking points migrated: {self.stats['points']}")
        print(f"  • Geofences migrated: {self.stats['geofences']}")
        print(f"  • Configurations migrated: {self.stats['configs']}")

        if self.stats["errors"]:
            print(f"\n⚠️ Errors encountered:")
            for error in self.stats["errors"]:
                print(f"  • {error}")

    def cleanup_old_data(self, days=90):
        """Clean up old tracking data"""
        print(f"\n🧹 Cleaning up tracking data older than {days} days...")

        conn = self.connect_dest()
        cursor = conn.cursor()

        try:
            # Count points to delete
            cursor.execute(
                """
                SELECT COUNT(*) FROM iot_gps_tracking_point
                WHERE timestamp < CURRENT_DATE - INTERVAL '%s days'
            """,
                (days,),
            )

            count = cursor.fetchone()[0]

            if count > 0:
                print(f"  ⚠️ Found {count} points to delete")

                # Delete old points
                cursor.execute(
                    """
                    DELETE FROM iot_gps_tracking_point
                    WHERE timestamp < CURRENT_DATE - INTERVAL '%s days'
                """,
                    (days,),
                )

                conn.commit()
                print(f"  ✅ Deleted {count} old tracking points")
            else:
                print(f"  ✅ No old points to delete")

        except Exception as e:
            conn.rollback()
            print(f"  ❌ Cleanup failed: {e}")

        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="IoT GPS Data Migration Tool")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Migrate command
    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate data from legacy module"
    )
    migrate_parser.add_argument("--source-db", required=True, help="Source database")
    migrate_parser.add_argument("--dest-db", required=True, help="Destination database")
    migrate_parser.add_argument("--source-user", default="odoo", help="Source DB user")
    migrate_parser.add_argument(
        "--source-password", default="odoo", help="Source DB password"
    )
    migrate_parser.add_argument(
        "--dest-user", default="odoo", help="Destination DB user"
    )
    migrate_parser.add_argument(
        "--dest-password", default="odoo", help="Destination DB password"
    )
    migrate_parser.add_argument(
        "--source-host", default="localhost", help="Source DB host"
    )
    migrate_parser.add_argument(
        "--dest-host", default="localhost", help="Destination DB host"
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export data to CSV")
    export_parser.add_argument("--db", required=True, help="Database name")
    export_parser.add_argument(
        "--output", default="gps_export", help="Output directory"
    )
    export_parser.add_argument("--db-user", default="odoo", help="Database user")
    export_parser.add_argument(
        "--db-password", default="odoo", help="Database password"
    )
    export_parser.add_argument("--db-host", default="localhost", help="Database host")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old data")
    cleanup_parser.add_argument("--db", required=True, help="Database name")
    cleanup_parser.add_argument("--days", type=int, default=90, help="Days to keep")
    cleanup_parser.add_argument("--db-user", default="odoo", help="Database user")
    cleanup_parser.add_argument(
        "--db-password", default="odoo", help="Database password"
    )
    cleanup_parser.add_argument("--db-host", default="localhost", help="Database host")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "migrate":
        migrator = DataMigrator(
            source_db=args.source_db,
            dest_db=args.dest_db,
            source_user=args.source_user,
            source_password=args.source_password,
            dest_user=args.dest_user,
            dest_password=args.dest_password,
            source_host=args.source_host,
            dest_host=args.dest_host,
        )
        migrator.migrate_from_legacy_gps_tracking()

    elif args.command == "export":
        migrator = DataMigrator(
            source_db=args.db,
            dest_db=args.db,
            source_user=args.db_user,
            source_password=args.db_password,
            dest_user=args.db_user,
            dest_password=args.db_password,
            source_host=args.db_host,
            dest_host=args.db_host,
        )
        migrator.export_to_csv(args.output)

    elif args.command == "cleanup":
        migrator = DataMigrator(
            source_db=args.db,
            dest_db=args.db,
            source_user=args.db_user,
            source_password=args.db_password,
            dest_user=args.db_user,
            dest_password=args.db_password,
            source_host=args.db_host,
            dest_host=args.db_host,
        )
        migrator.cleanup_old_data(args.days)


if __name__ == "__main__":
    main()
