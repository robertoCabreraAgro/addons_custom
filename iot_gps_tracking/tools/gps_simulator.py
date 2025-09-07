#!/usr/bin/env python3
"""
GPS Simulator and Demo Data Generator for IoT GPS Tracking
Can be used for real-time simulation or generating demo data
"""

import json
import random
import time
import requests
import argparse
import csv
import math
from datetime import datetime, timedelta


class GPSSimulator:
    """Simulate GPS device movements and generate demo data"""

    def __init__(self, base_url=None, imei=None, start_lat=40.7128, start_lon=-74.0060):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.imei = imei or f"SIM{random.randint(100000000, 999999999)}"
        self.current_lat = start_lat
        self.current_lon = start_lon
        self.current_speed = 0
        self.current_heading = random.randint(0, 360)
        self.ignition = True
        self.fuel_level = random.randint(50, 100)
        self.battery_level = random.randint(80, 100)
        self.odometer = random.randint(10000, 50000)

    def simulate_movement(self):
        """Simulate realistic vehicle movement"""
        # Random speed changes
        speed_change = random.uniform(-5, 5)
        self.current_speed = max(0, min(120, self.current_speed + speed_change))

        # Random heading changes
        heading_change = random.uniform(-10, 10)
        self.current_heading = (self.current_heading + heading_change) % 360

        # Calculate new position based on speed and heading
        if self.current_speed > 0:
            # Convert speed from km/h to m/s
            speed_ms = self.current_speed / 3.6

            # Calculate distance traveled in 1 second
            distance = speed_ms / 111000  # Rough conversion to degrees

            # Calculate new position
            heading_rad = math.radians(self.current_heading)
            self.current_lat += distance * math.cos(heading_rad)
            self.current_lon += distance * math.sin(heading_rad)

            # Update odometer
            self.odometer += speed_ms / 1000  # Convert to km

        # Simulate fuel consumption
        if self.ignition and self.current_speed > 0:
            self.fuel_level = max(0, self.fuel_level - random.uniform(0, 0.1))

        # Simulate battery drain
        self.battery_level = max(0, self.battery_level - random.uniform(0, 0.05))

    def generate_gps_data(self, timestamp=None):
        """Generate GPS data packet"""
        self.simulate_movement()

        return {
            "imei": self.imei,
            "data": {
                "latitude": round(self.current_lat, 7),
                "longitude": round(self.current_lon, 7),
                "timestamp": timestamp or datetime.now().isoformat(),
                "speed": round(self.current_speed, 1),
                "altitude": random.randint(50, 150),
                "satellites": random.randint(6, 12),
                "accuracy": round(random.uniform(3, 10), 1),
                "heading": round(self.current_heading, 1),
                "battery": round(self.battery_level, 1),
                "ignition": self.ignition,
                "movement": self.current_speed > 0,
                "odometer": round(self.odometer, 1),
                "fuel_level": round(self.fuel_level, 1),
                "engine_temp": random.randint(70, 95) if self.ignition else 20,
                "engine_rpm": (
                    random.randint(800, 3000)
                    if self.ignition and self.current_speed > 0
                    else 0
                ),
                "battery_voltage": round(random.uniform(12.0, 14.5), 1),
                "external_voltage": (
                    round(random.uniform(13.0, 14.5), 1) if self.ignition else 0
                ),
                "gsm_signal": random.randint(3, 5),
            },
        }

    def send_data(self, data):
        """Send data to webhook endpoint"""
        if not self.base_url:
            return False

        url = f"{self.base_url}/gps/iot/webhook"
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                result = response.json()
                return result.get("status") == "success"
            else:
                print(f"Error: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"Error sending data: {e}")
            return False

    def simulate_route(self, duration_minutes=10, interval_seconds=30):
        """Simulate a route for specified duration"""
        if not self.base_url:
            print("Error: No base URL specified for real-time simulation")
            return

        print(f"Starting GPS simulation for device {self.imei}")
        print(f"Duration: {duration_minutes} minutes")
        print(f"Update interval: {interval_seconds} seconds")
        print("-" * 50)

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        update_count = 0

        # Start with some initial speed
        self.current_speed = random.uniform(30, 60)

        while time.time() < end_time:
            # Generate and send GPS data
            data = self.generate_gps_data()

            # Print current status
            print(
                f"\n[{datetime.now().strftime('%H:%M:%S')}] Update #{update_count + 1}"
            )
            print(
                f"Position: {data['data']['latitude']:.6f}, {data['data']['longitude']:.6f}"
            )
            print(
                f"Speed: {data['data']['speed']} km/h | Heading: {data['data']['heading']}°"
            )
            print(
                f"Fuel: {data['data']['fuel_level']:.1f}% | Battery: {data['data']['battery']:.1f}%"
            )

            # Send to server
            if self.send_data(data):
                print("✓ Data sent successfully")
            else:
                print("✗ Failed to send data")

            update_count += 1

            # Random events
            if random.random() < 0.1:  # 10% chance of stopping
                print("🛑 Vehicle stopped")
                self.current_speed = 0
            elif (
                random.random() < 0.1 and self.current_speed == 0
            ):  # 10% chance of starting
                print("🚗 Vehicle started moving")
                self.current_speed = random.uniform(20, 50)

            # Wait for next update
            time.sleep(interval_seconds)

        print("\n" + "=" * 50)
        print(f"Simulation completed!")
        print(f"Total updates sent: {update_count}")
        print(f"Final position: {self.current_lat:.6f}, {self.current_lon:.6f}")
        print(f"Total distance: {self.odometer - random.randint(10000, 50000):.1f} km")


def calculate_heading(pos1, pos2):
    """Calculate heading between two positions"""
    lat1, lon1 = pos1
    lat2, lon2 = pos2

    dlon = lon2 - lon1
    x = math.cos(math.radians(lat2)) * math.sin(math.radians(dlon))
    y = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(
        math.radians(lat1)
    ) * math.cos(math.radians(lat2)) * math.cos(math.radians(dlon))

    heading = math.degrees(math.atan2(x, y))
    return (heading + 360) % 360


def generate_demo_tracking_data(hours=24, points_per_hour=2):
    """Generate demo tracking points for multiple vehicles"""

    # Define routes for each vehicle
    routes = {
        "truck_01": {
            "imei": "352625100123001",
            "start": (40.7128, -74.0060),  # Warehouse
            "waypoints": [
                (40.7200, -74.0000),
                (40.7300, -73.9950),
                (40.7400, -73.9900),
                (40.7500, -73.9870),
                (40.7580, -73.9855),  # Customer Zone A
            ],
            "speed_range": (30, 60),
            "stops": [5],  # Stop at Customer Zone A
        },
        "truck_02": {
            "imei": "352625100123002",
            "start": (40.7580, -73.9855),  # Currently at Customer Zone
            "waypoints": [],  # Stationary
            "speed_range": (0, 0),
            "stops": [],
        },
        "van_01": {
            "imei": "352625100123003",
            "start": (40.7128, -74.0060),  # Warehouse
            "waypoints": [
                (40.7000, -74.0100),
                (40.6950, -74.0200),
                (40.6900, -74.0300),
                (40.6892, -74.0445),  # Current position
            ],
            "speed_range": (40, 80),
            "stops": [],
        },
        "asset_01": {
            "imei": "352625100123004",
            "start": (40.7489, -73.9680),  # Fixed position
            "waypoints": [],  # Stationary asset
            "speed_range": (0, 0),
            "stops": [],
        },
    }

    tracking_points = []
    base_time = datetime.now() - timedelta(hours=hours)

    for device_name, route in routes.items():
        device_id = f"demo_gps_device_{device_name}"
        simulator = GPSSimulator(
            imei=route["imei"], start_lat=route["start"][0], start_lon=route["start"][1]
        )

        if route["waypoints"]:
            # Generate moving route
            total_points = hours * points_per_hour
            points_per_segment = total_points // (len(route["waypoints"]) + 1)

            current_pos = route["start"]
            current_time = base_time

            for i, waypoint in enumerate(route["waypoints"] + [route["waypoints"][-1]]):
                # Generate points between current position and waypoint
                for j in range(points_per_segment):
                    # Interpolate position
                    progress = j / points_per_segment
                    lat = current_pos[0] + (waypoint[0] - current_pos[0]) * progress
                    lon = current_pos[1] + (waypoint[1] - current_pos[1]) * progress

                    # Add some random variation
                    lat += random.uniform(-0.0005, 0.0005)
                    lon += random.uniform(-0.0005, 0.0005)

                    # Set simulator position
                    simulator.current_lat = lat
                    simulator.current_lon = lon

                    # Determine if stopped
                    is_stopped = i in route["stops"] and j > points_per_segment * 0.8

                    if is_stopped:
                        simulator.current_speed = 0
                        simulator.ignition = False
                    else:
                        simulator.current_speed = random.uniform(*route["speed_range"])
                        simulator.ignition = True
                        simulator.current_heading = calculate_heading(
                            current_pos, waypoint
                        )

                    # Generate data point
                    point = simulator.generate_gps_data(current_time.isoformat())
                    point["device_id"] = device_id
                    tracking_points.append(point)

                    current_time += timedelta(hours=1 / points_per_hour)

                current_pos = waypoint

        else:
            # Generate stationary points
            for hour in range(hours * points_per_hour):
                simulator.current_speed = 0
                simulator.ignition = False

                point = simulator.generate_gps_data(
                    (base_time + timedelta(hours=hour / points_per_hour)).isoformat()
                )
                point["device_id"] = device_id
                tracking_points.append(point)

    return tracking_points


def generate_xml_records(tracking_points):
    """Generate XML records for tracking points"""
    xml_records = []

    for i, point in enumerate(tracking_points):
        record_id = f"demo_tracking_point_{i:04d}"

        xml_record = f"""
        <record id="{record_id}" model="iot.gps.tracking.point">
            <field name="iot_device_id" ref="{point['device_id']}"/>
            <field name="timestamp">{point['data']['timestamp']}</field>
            <field name="latitude">{point['data']['latitude']}</field>
            <field name="longitude">{point['data']['longitude']}</field>
            <field name="altitude">{point['data']['altitude']}</field>
            <field name="speed">{point['data']['speed']}</field>
            <field name="satellites">{point['data']['satellites']}</field>
            <field name="accuracy">{point['data']['accuracy']}</field>
            <field name="heading">{point['data']['heading']}</field>
            <field name="battery_level">{point['data']['battery']}</field>
            <field name="ignition">{point['data']['ignition']}</field>
            <field name="movement">{point['data']['movement']}</field>
            <field name="odometer">{point['data']['odometer']}</field>
            <field name="fuel_level">{point['data']['fuel_level']}</field>
            <field name="engine_temp">{point['data']['engine_temp']}</field>
            <field name="engine_rpm">{point['data']['engine_rpm']}</field>
        </record>"""

        xml_records.append(xml_record)

    return xml_records


def generate_csv_sample(output_file="sample_gps_data.csv"):
    """Generate a sample CSV file for testing"""
    print(f"Generating sample CSV file: {output_file}")

    headers = [
        "imei",
        "timestamp",
        "latitude",
        "longitude",
        "speed",
        "altitude",
        "satellites",
        "accuracy",
        "heading",
        "ignition",
        "movement",
        "battery",
        "fuel_level",
        "odometer",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()

        # Use simulator to generate realistic data
        simulator = GPSSimulator(imei="123456789012345")
        base_time = datetime.now()

        for i in range(100):
            # Generate data point
            data = simulator.generate_gps_data(
                (base_time + timedelta(minutes=i)).isoformat()
            )

            row = {
                "imei": data["imei"],
                "timestamp": data["data"]["timestamp"],
                "latitude": data["data"]["latitude"],
                "longitude": data["data"]["longitude"],
                "speed": data["data"]["speed"],
                "altitude": data["data"]["altitude"],
                "satellites": data["data"]["satellites"],
                "accuracy": data["data"]["accuracy"],
                "heading": data["data"]["heading"],
                "ignition": str(data["data"]["ignition"]).lower(),
                "movement": str(data["data"]["movement"]).lower(),
                "battery": data["data"]["battery"],
                "fuel_level": data["data"]["fuel_level"],
                "odometer": data["data"]["odometer"],
            }
            writer.writerow(row)

    print(f"✓ Sample CSV generated with 100 records")
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="GPS Simulator and Demo Data Generator"
    )

    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")

    # Real-time simulation mode
    sim_parser = subparsers.add_parser("simulate", help="Real-time GPS simulation")
    sim_parser.add_argument(
        "--url",
        default="http://localhost:8069",
        help="Odoo server URL (default: http://localhost:8069)",
    )
    sim_parser.add_argument(
        "--imei",
        help="Device IMEI (default: random)",
    )
    sim_parser.add_argument(
        "--lat",
        type=float,
        default=40.7128,
        help="Starting latitude (default: 40.7128)",
    )
    sim_parser.add_argument(
        "--lon",
        type=float,
        default=-74.0060,
        help="Starting longitude (default: -74.0060)",
    )
    sim_parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Simulation duration in minutes (default: 10)",
    )
    sim_parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Update interval in seconds (default: 30)",
    )

    # Demo data generation mode
    demo_parser = subparsers.add_parser("generate-demo", help="Generate demo data")
    demo_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours of data to generate (default: 24)",
    )
    demo_parser.add_argument(
        "--points-per-hour",
        type=int,
        default=2,
        help="Data points per hour (default: 2)",
    )
    demo_parser.add_argument(
        "--format",
        choices=["xml", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )

    # CSV sample generation mode
    csv_parser = subparsers.add_parser("generate-csv", help="Generate sample CSV")
    csv_parser.add_argument(
        "--output",
        default="sample_gps_data.csv",
        help="Output file name (default: sample_gps_data.csv)",
    )

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        return

    if args.mode == "simulate":
        # Real-time simulation
        simulator = GPSSimulator(
            base_url=args.url, imei=args.imei, start_lat=args.lat, start_lon=args.lon
        )
        try:
            simulator.simulate_route(args.duration, args.interval)
        except KeyboardInterrupt:
            print("\n\nSimulation stopped by user")

    elif args.mode == "generate-demo":
        # Generate demo data
        print(f"Generating {args.hours} hours of demo tracking data...")
        points = generate_demo_tracking_data(args.hours, args.points_per_hour)

        print(f"Generated {len(points)} tracking points")

        # Save as JSON
        if args.format in ["json", "both"]:
            with open("demo_tracking_points.json", "w") as f:
                json.dump(points, f, indent=2)
            print("✓ Saved to demo_tracking_points.json")

        # Generate XML
        if args.format in ["xml", "both"]:
            xml_records = generate_xml_records(points)
            xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <!-- Demo Tracking Points Generated -->
        {"".join(xml_records)}
    </data>
</odoo>"""

            with open("demo_tracking_points.xml", "w") as f:
                f.write(xml_content)
            print("✓ Saved to demo_tracking_points.xml")

        # Print summary
        print("\nSummary by device:")
        device_counts = {}
        for point in points:
            device = point["device_id"]
            device_counts[device] = device_counts.get(device, 0) + 1

        for device, count in device_counts.items():
            print(f"  - {device}: {count} points")

    elif args.mode == "generate-csv":
        # Generate CSV sample
        generate_csv_sample(args.output)


if __name__ == "__main__":
    main()
