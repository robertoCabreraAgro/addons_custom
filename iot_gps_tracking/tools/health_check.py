#!/usr/bin/env python3
"""
Health Check Tool for IoT GPS Tracking Module
Verify module installation and functionality
"""

import sys
import json
import requests
import argparse
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql


class HealthChecker:
    """Check health of IoT GPS Tracking module"""

    def __init__(
        self,
        db_name,
        db_user="odoo",
        db_password="odoo",
        db_host="localhost",
        base_url="http://localhost:8069",
    ):
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.db_host = db_host
        self.base_url = base_url.rstrip("/")
        self.checks_passed = 0
        self.checks_failed = 0
        self.issues = []

    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            conn = psycopg2.connect(
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password,
                host=self.db_host,
            )
            return conn
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return None

    def check_database(self):
        """Check database tables and indexes"""
        print("\n🔍 Checking Database...")
        conn = self.connect_db()
        if not conn:
            self.checks_failed += 1
            self.issues.append("Cannot connect to database")
            return False

        cursor = conn.cursor()
        all_good = True

        # Check tables exist
        tables = [
            "iot_device",
            "iot_gps_tracking_point",
            "iot_gps_config",
            "iot_gps_geofence",
        ]

        for table in tables:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """,
                (table,),
            )
            exists = cursor.fetchone()[0]

            if exists:
                print(f"  ✅ Table {table} exists")
                self.checks_passed += 1

                # Check row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"     → {count} records")
            else:
                print(f"  ❌ Table {table} missing")
                self.checks_failed += 1
                self.issues.append(f"Table {table} not found")
                all_good = False

        # Check PostGIS extension
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_extension WHERE extname = 'postgis'
            )
        """
        )
        has_postgis = cursor.fetchone()[0]

        if has_postgis:
            print(f"  ✅ PostGIS extension installed")
            self.checks_passed += 1
        else:
            print(f"  ⚠️  PostGIS extension not installed (optional)")

        # Check indexes
        cursor.execute(
            """
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'iot_gps_tracking_point'
            AND indexname LIKE '%idx%'
        """
        )
        indexes = cursor.fetchall()

        if indexes:
            print(f"  ✅ Performance indexes found ({len(indexes)} indexes)")
            self.checks_passed += 1
        else:
            print(f"  ⚠️  No performance indexes found")

        conn.close()
        return all_good

    def check_module_installed(self):
        """Check if module is installed in Odoo"""
        print("\n🔍 Checking Module Installation...")
        conn = self.connect_db()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT state, latest_version 
            FROM ir_module_module 
            WHERE name = 'iot_gps_tracking'
        """
        )
        result = cursor.fetchone()

        if result:
            state, version = result
            if state == "installed":
                print(f"  ✅ Module installed (version: {version})")
                self.checks_passed += 1
                conn.close()
                return True
            else:
                print(f"  ❌ Module not installed (state: {state})")
                self.checks_failed += 1
                self.issues.append(f"Module state is {state}, not installed")
        else:
            print(f"  ❌ Module not found")
            self.checks_failed += 1
            self.issues.append("Module iot_gps_tracking not found")

        conn.close()
        return False

    def check_dependencies(self):
        """Check module dependencies"""
        print("\n🔍 Checking Dependencies...")
        conn = self.connect_db()
        if not conn:
            return False

        cursor = conn.cursor()
        dependencies = ["iot", "iot_base", "base_geoengine"]
        all_good = True

        for dep in dependencies:
            cursor.execute(
                """
                SELECT state FROM ir_module_module WHERE name = %s
            """,
                (dep,),
            )
            result = cursor.fetchone()

            if result and result[0] == "installed":
                print(f"  ✅ {dep} installed")
                self.checks_passed += 1
            else:
                print(f"  ❌ {dep} not installed")
                self.checks_failed += 1
                self.issues.append(f"Dependency {dep} not installed")
                all_good = False

        conn.close()
        return all_good

    def check_cron_jobs(self):
        """Check if cron jobs are active"""
        print("\n🔍 Checking Cron Jobs...")
        conn = self.connect_db()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name, active, nextcall 
            FROM ir_cron 
            WHERE name LIKE 'GPS:%'
            ORDER BY name
        """
        )

        cron_jobs = cursor.fetchall()

        if cron_jobs:
            for name, active, nextcall in cron_jobs:
                if active:
                    print(f"  ✅ {name}")
                    print(f"     → Next run: {nextcall}")
                    self.checks_passed += 1
                else:
                    print(f"  ⚠️  {name} (inactive)")
        else:
            print(f"  ❌ No GPS cron jobs found")
            self.checks_failed += 1
            self.issues.append("No GPS cron jobs found")

        conn.close()
        return len(cron_jobs) > 0

    def check_api_endpoint(self):
        """Test API endpoint availability"""
        print("\n🔍 Checking API Endpoints...")

        # Test webhook endpoint
        url = f"{self.base_url}/gps/iot/webhook"
        try:
            response = requests.post(
                url, json={}, headers={"Content-Type": "application/json"}, timeout=5
            )
            if response.status_code in [200, 400]:  # 400 is expected for empty data
                print(f"  ✅ Webhook endpoint accessible")
                self.checks_passed += 1
            else:
                print(f"  ❌ Webhook endpoint returned {response.status_code}")
                self.checks_failed += 1
                self.issues.append(f"Webhook endpoint HTTP {response.status_code}")
        except Exception as e:
            print(f"  ❌ Cannot reach webhook endpoint: {e}")
            self.checks_failed += 1
            self.issues.append(f"Webhook endpoint unreachable")

        # Test status endpoint
        url = f"{self.base_url}/gps/iot/status/TEST123"
        try:
            response = requests.get(url, timeout=5)
            print(f"  ✅ Status endpoint accessible")
            self.checks_passed += 1
        except Exception as e:
            print(f"  ⚠️  Status endpoint not accessible (may require auth)")

    def check_recent_activity(self):
        """Check for recent GPS activity"""
        print("\n🔍 Checking Recent Activity...")
        conn = self.connect_db()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check for recent tracking points
        cursor.execute(
            """
            SELECT COUNT(*), MAX(timestamp) 
            FROM iot_gps_tracking_point 
            WHERE timestamp > %s
        """,
            (datetime.now() - timedelta(days=7),),
        )

        count, last_point = cursor.fetchone()

        if count > 0:
            print(f"  ✅ {count} tracking points in last 7 days")
            print(f"     → Last point: {last_point}")
            self.checks_passed += 1
        else:
            print(f"  ℹ️  No recent tracking points")

        # Check for active devices
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM iot_device 
            WHERE type = 'gps_tracker' 
            AND gps_tracking_enabled = true
        """
        )

        active_count = cursor.fetchone()[0]

        if active_count > 0:
            print(f"  ✅ {active_count} active GPS devices")
            self.checks_passed += 1
        else:
            print(f"  ℹ️  No active GPS devices")

        conn.close()
        return True

    def check_performance(self):
        """Check performance metrics"""
        print("\n🔍 Checking Performance...")
        conn = self.connect_db()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check tracking points table size
        cursor.execute(
            """
            SELECT 
                pg_size_pretty(pg_total_relation_size('iot_gps_tracking_point')) as size,
                COUNT(*) as count
            FROM iot_gps_tracking_point
        """
        )

        size, count = cursor.fetchone()
        print(f"  ℹ️  Tracking points: {count} records, {size}")

        # Check query performance
        start_time = datetime.now()
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM iot_gps_tracking_point 
            WHERE timestamp > CURRENT_DATE - INTERVAL '1 day'
        """
        )
        query_time = (datetime.now() - start_time).total_seconds()

        if query_time < 1:
            print(f"  ✅ Query performance good ({query_time:.3f}s)")
            self.checks_passed += 1
        else:
            print(f"  ⚠️  Query performance slow ({query_time:.3f}s)")

        conn.close()
        return True

    def run_all_checks(self):
        """Run all health checks"""
        print("=" * 50)
        print("IoT GPS Tracking Module Health Check")
        print("=" * 50)
        print(f"Database: {self.db_name}")
        print(f"URL: {self.base_url}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Run checks
        self.check_module_installed()
        self.check_dependencies()
        self.check_database()
        self.check_cron_jobs()
        self.check_api_endpoint()
        self.check_recent_activity()
        self.check_performance()

        # Summary
        print("\n" + "=" * 50)
        print("Health Check Summary")
        print("=" * 50)
        print(f"✅ Checks passed: {self.checks_passed}")
        print(f"❌ Checks failed: {self.checks_failed}")

        if self.issues:
            print("\n⚠️  Issues Found:")
            for issue in self.issues:
                print(f"  • {issue}")
        else:
            print("\n🎉 All critical checks passed!")

        # Overall status
        if self.checks_failed == 0:
            print("\n✨ Module Status: HEALTHY")
            return 0
        elif self.checks_failed <= 2:
            print("\n⚠️  Module Status: WARNING")
            return 1
        else:
            print("\n❌ Module Status: CRITICAL")
            return 2


def main():
    parser = argparse.ArgumentParser(description="IoT GPS Tracking Module Health Check")
    parser.add_argument("--db", required=True, help="Database name")
    parser.add_argument("--db-user", default="odoo", help="Database user")
    parser.add_argument("--db-password", default="odoo", help="Database password")
    parser.add_argument("--db-host", default="localhost", help="Database host")
    parser.add_argument(
        "--url", default="http://localhost:8069", help="Odoo server URL"
    )

    args = parser.parse_args()

    # Create health checker
    checker = HealthChecker(
        db_name=args.db,
        db_user=args.db_user,
        db_password=args.db_password,
        db_host=args.db_host,
        base_url=args.url,
    )

    # Run checks
    exit_code = checker.run_all_checks()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
