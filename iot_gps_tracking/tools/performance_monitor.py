#!/usr/bin/env python3
"""
Performance Monitoring Tool for IoT GPS Tracking
Monitor and analyze GPS tracking system performance
"""

import time
import json
import psycopg2
import argparse
from datetime import datetime, timedelta
import statistics
import matplotlib.pyplot as plt
from collections import defaultdict


class PerformanceMonitor:
    """Monitor GPS tracking system performance metrics"""

    def __init__(
        self, db_name, db_user="odoo", db_password="odoo", db_host="localhost"
    ):
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.db_host = db_host
        self.metrics = defaultdict(list)

    def connect_db(self):
        """Connect to PostgreSQL database"""
        return psycopg2.connect(
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
            host=self.db_host,
        )

    def measure_query_performance(self):
        """Measure database query performance"""
        print("\n📊 Measuring Query Performance...")
        conn = self.connect_db()
        cursor = conn.cursor()

        queries = [
            (
                "Recent points",
                """
                SELECT COUNT(*) FROM iot_gps_tracking_point 
                WHERE timestamp > CURRENT_DATE - INTERVAL '1 day'
            """,
            ),
            (
                "Device positions",
                """
                SELECT id, gps_last_latitude, gps_last_longitude 
                FROM iot_device 
                WHERE type = 'gps_tracker' AND gps_tracking_enabled = true
                LIMIT 100
            """,
            ),
            (
                "Geofence checks",
                """
                SELECT COUNT(*) FROM iot_gps_geofence 
                WHERE active = true
            """,
            ),
            (
                "Point aggregation",
                """
                SELECT 
                    iot_device_id,
                    DATE_TRUNC('hour', timestamp) as hour,
                    COUNT(*) as points,
                    AVG(speed) as avg_speed
                FROM iot_gps_tracking_point
                WHERE timestamp > CURRENT_DATE - INTERVAL '7 days'
                GROUP BY iot_device_id, hour
                LIMIT 1000
            """,
            ),
            (
                "Distance calculation",
                """
                SELECT 
                    iot_device_id,
                    SUM(
                        6371 * acos(
                            cos(radians(latitude)) * cos(radians(LAG(latitude) OVER (PARTITION BY iot_device_id ORDER BY timestamp))) *
                            cos(radians(LAG(longitude) OVER (PARTITION BY iot_device_id ORDER BY timestamp)) - radians(longitude)) +
                            sin(radians(latitude)) * sin(radians(LAG(latitude) OVER (PARTITION BY iot_device_id ORDER BY timestamp)))
                        )
                    ) as total_distance_km
                FROM iot_gps_tracking_point
                WHERE timestamp > CURRENT_DATE - INTERVAL '1 day'
                GROUP BY iot_device_id
            """,
            ),
        ]

        for name, query in queries:
            times = []
            for _ in range(5):  # Run each query 5 times
                start = time.time()
                cursor.execute(query)
                cursor.fetchall()
                elapsed = (time.time() - start) * 1000  # Convert to ms
                times.append(elapsed)

            avg_time = statistics.mean(times)
            std_dev = statistics.stdev(times) if len(times) > 1 else 0

            self.metrics["queries"].append(
                {
                    "name": name,
                    "avg_time": avg_time,
                    "std_dev": std_dev,
                    "min_time": min(times),
                    "max_time": max(times),
                }
            )

            status = "✅" if avg_time < 100 else "⚠️" if avg_time < 500 else "❌"
            print(f"  {status} {name}: {avg_time:.2f}ms (±{std_dev:.2f}ms)")

        conn.close()

    def analyze_data_growth(self):
        """Analyze data growth patterns"""
        print("\n📈 Analyzing Data Growth...")
        conn = self.connect_db()
        cursor = conn.cursor()

        # Get daily tracking point counts
        cursor.execute(
            """
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as points,
                COUNT(DISTINCT iot_device_id) as devices
            FROM iot_gps_tracking_point
            WHERE timestamp > CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(timestamp)
            ORDER BY date
        """
        )

        daily_data = cursor.fetchall()

        if daily_data:
            dates = [row[0] for row in daily_data]
            points = [row[1] for row in daily_data]
            devices = [row[2] for row in daily_data]

            avg_points_per_day = statistics.mean(points)
            growth_rate = (
                (points[-1] - points[0]) / len(points) if len(points) > 1 else 0
            )

            self.metrics["growth"] = {
                "avg_points_per_day": avg_points_per_day,
                "growth_rate": growth_rate,
                "total_days": len(dates),
                "max_points_day": max(points),
                "min_points_day": min(points),
            }

            print(f"  📊 Average points per day: {avg_points_per_day:.0f}")
            print(f"  📈 Daily growth rate: {growth_rate:.1f} points/day")
            print(f"  🔝 Peak day: {max(points)} points")

        # Table sizes
        cursor.execute(
            """
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables
            WHERE tablename IN ('iot_gps_tracking_point', 'iot_device', 'iot_gps_geofence', 'iot_gps_config')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """
        )

        print("\n  Table Sizes:")
        for row in cursor.fetchall():
            print(f"    • {row[1]}: {row[2]}")

        conn.close()

    def check_index_usage(self):
        """Check index usage and efficiency"""
        print("\n🔍 Checking Index Usage...")
        conn = self.connect_db()
        cursor = conn.cursor()

        # Get index usage statistics
        cursor.execute(
            """
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
                AND tablename IN ('iot_gps_tracking_point', 'iot_device', 'iot_gps_geofence')
            ORDER BY idx_scan DESC
        """
        )

        indexes = cursor.fetchall()

        for idx in indexes:
            scans = idx[3]
            status = "✅" if scans > 100 else "⚠️" if scans > 0 else "❌"
            print(f"  {status} {idx[2]}: {scans} scans, {idx[6]} size")

            if scans == 0:
                self.metrics["unused_indexes"].append(idx[2])

        # Check for missing indexes
        cursor.execute(
            """
            SELECT 
                schemaname,
                tablename,
                attname,
                n_distinct,
                correlation
            FROM pg_stats
            WHERE schemaname = 'public'
                AND tablename = 'iot_gps_tracking_point'
                AND n_distinct > 100
                AND attname NOT IN (
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = 'iot_gps_tracking_point'::regclass
                )
        """
        )

        missing = cursor.fetchall()
        if missing:
            print("\n  ⚠️ Potential missing indexes:")
            for col in missing:
                print(f"    • {col[1]}.{col[2]} (distinct values: {col[3]})")

        conn.close()

    def monitor_connections(self):
        """Monitor database connections"""
        print("\n🔗 Monitoring Database Connections...")
        conn = self.connect_db()
        cursor = conn.cursor()

        # Get connection statistics
        cursor.execute(
            """
            SELECT 
                state,
                COUNT(*) as count
            FROM pg_stat_activity
            WHERE datname = %s
            GROUP BY state
        """,
            (self.db_name,),
        )

        for state, count in cursor.fetchall():
            print(f"  • {state or 'active'}: {count} connections")

        # Check for long-running queries
        cursor.execute(
            """
            SELECT 
                pid,
                usename,
                EXTRACT(EPOCH FROM (NOW() - query_start)) as duration,
                LEFT(query, 50) as query_snippet
            FROM pg_stat_activity
            WHERE datname = %s
                AND state = 'active'
                AND query_start < NOW() - INTERVAL '1 minute'
            ORDER BY duration DESC
            LIMIT 5
        """,
            (self.db_name,),
        )

        long_queries = cursor.fetchall()
        if long_queries:
            print("\n  ⚠️ Long-running queries:")
            for q in long_queries:
                print(f"    • PID {q[0]} ({q[1]}): {q[2]:.0f}s - {q[3]}...")

        conn.close()

    def check_api_performance(self, base_url="http://localhost:8069"):
        """Test API endpoint performance"""
        print(f"\n🌐 Testing API Performance ({base_url})...")

        try:
            import requests

            endpoints = [
                ("/gps/iot/webhook", "POST", {"imei": "TEST", "data": {}}),
                ("/gps/iot/status/TEST", "GET", None),
            ]

            for endpoint, method, data in endpoints:
                url = base_url + endpoint
                times = []

                for _ in range(10):
                    start = time.time()
                    try:
                        if method == "POST":
                            response = requests.post(url, json=data, timeout=5)
                        else:
                            response = requests.get(url, timeout=5)
                        elapsed = (time.time() - start) * 1000
                        times.append(elapsed)
                    except Exception:
                        times.append(5000)  # Timeout as 5000ms

                if times:
                    avg_time = statistics.mean(times)
                    status = "✅" if avg_time < 100 else "⚠️" if avg_time < 500 else "❌"
                    print(f"  {status} {method} {endpoint}: {avg_time:.2f}ms")

                    self.metrics["api"].append(
                        {"endpoint": endpoint, "method": method, "avg_time": avg_time}
                    )
        except ImportError:
            print("  ⚠️ requests library not available, skipping API tests")

    def generate_report(self):
        """Generate performance report"""
        print("\n" + "=" * 50)
        print("Performance Report")
        print("=" * 50)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Query Performance Summary
        if self.metrics["queries"]:
            print("\n📊 Query Performance:")
            slow_queries = [q for q in self.metrics["queries"] if q["avg_time"] > 500]
            if slow_queries:
                print("  ❌ Slow queries detected:")
                for q in slow_queries:
                    print(f"    • {q['name']}: {q['avg_time']:.2f}ms")
            else:
                print("  ✅ All queries performing well")

        # Growth Analysis
        if "growth" in self.metrics:
            growth = self.metrics["growth"]
            print(f"\n📈 Data Growth:")
            print(f"  • Average: {growth['avg_points_per_day']:.0f} points/day")
            print(f"  • Growth rate: {growth['growth_rate']:.1f} points/day²")

            # Projection
            days_to_million = (1000000 - growth["avg_points_per_day"] * 30) / growth[
                "avg_points_per_day"
            ]
            if days_to_million > 0:
                print(f"  • Projected to reach 1M points in {days_to_million:.0f} days")

        # Unused Indexes
        if self.metrics["unused_indexes"]:
            print(f"\n⚠️ Unused Indexes:")
            for idx in self.metrics["unused_indexes"]:
                print(f"  • {idx}")

        # API Performance
        if self.metrics["api"]:
            print(f"\n🌐 API Performance:")
            for api in self.metrics["api"]:
                status = "✅" if api["avg_time"] < 100 else "⚠️"
                print(
                    f"  {status} {api['method']} {api['endpoint']}: {api['avg_time']:.2f}ms"
                )

        # Overall Health Score
        score = 100

        # Deduct points for issues
        slow_queries = len([q for q in self.metrics["queries"] if q["avg_time"] > 500])
        score -= slow_queries * 10
        score -= len(self.metrics["unused_indexes"]) * 5

        slow_apis = len([a for a in self.metrics["api"] if a["avg_time"] > 500])
        score -= slow_apis * 10

        score = max(0, score)

        print(f"\n🏆 Overall Performance Score: {score}/100")

        if score >= 90:
            print("✨ Excellent performance!")
        elif score >= 70:
            print("✅ Good performance with minor issues")
        elif score >= 50:
            print("⚠️ Performance needs attention")
        else:
            print("❌ Critical performance issues detected")

        return score

    def save_metrics(self, filename="performance_metrics.json"):
        """Save metrics to JSON file"""
        with open(filename, "w") as f:
            # Convert defaultdict to regular dict for JSON serialization
            metrics_dict = dict(self.metrics)
            json.dump(metrics_dict, f, indent=2, default=str)
        print(f"\n💾 Metrics saved to {filename}")


def main():
    parser = argparse.ArgumentParser(description="IoT GPS Performance Monitor")
    parser.add_argument("--db", required=True, help="Database name")
    parser.add_argument("--db-user", default="odoo", help="Database user")
    parser.add_argument("--db-password", default="odoo", help="Database password")
    parser.add_argument("--db-host", default="localhost", help="Database host")
    parser.add_argument(
        "--url", default="http://localhost:8069", help="Odoo server URL"
    )
    parser.add_argument("--save", action="store_true", help="Save metrics to file")

    args = parser.parse_args()

    # Create monitor
    monitor = PerformanceMonitor(
        db_name=args.db,
        db_user=args.db_user,
        db_password=args.db_password,
        db_host=args.db_host,
    )

    # Run monitoring
    try:
        monitor.measure_query_performance()
        monitor.analyze_data_growth()
        monitor.check_index_usage()
        monitor.monitor_connections()
        monitor.check_api_performance(args.url)

        # Generate report
        score = monitor.generate_report()

        # Save metrics if requested
        if args.save:
            monitor.save_metrics()

        # Exit with appropriate code
        if score >= 70:
            exit(0)
        elif score >= 50:
            exit(1)
        else:
            exit(2)

    except Exception as e:
        print(f"\n❌ Error during monitoring: {e}")
        exit(3)


if __name__ == "__main__":
    main()
