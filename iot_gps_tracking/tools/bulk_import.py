#!/usr/bin/env python3
"""
Bulk Import Tool for GPS Tracking Data
Import historical GPS data from CSV files
"""

import csv
import json
import requests
import argparse
from datetime import datetime
import os
import sys


class BulkImporter:
    """Import GPS tracking data from CSV files"""

    def __init__(self, base_url, batch_size=100):
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self.success_count = 0
        self.error_count = 0
        self.errors = []

    def parse_csv_row(self, row, column_mapping):
        """Parse CSV row to GPS data format"""
        try:
            data = {
                "imei": row.get(column_mapping.get("imei", "imei"), ""),
                "data": {
                    "latitude": float(
                        row.get(column_mapping.get("latitude", "latitude"), 0)
                    ),
                    "longitude": float(
                        row.get(column_mapping.get("longitude", "longitude"), 0)
                    ),
                    "timestamp": row.get(
                        column_mapping.get("timestamp", "timestamp"), ""
                    ),
                    "speed": float(row.get(column_mapping.get("speed", "speed"), 0)),
                    "altitude": float(
                        row.get(column_mapping.get("altitude", "altitude"), 0)
                    ),
                    "satellites": int(
                        row.get(column_mapping.get("satellites", "satellites"), 0)
                    ),
                    "accuracy": float(
                        row.get(column_mapping.get("accuracy", "accuracy"), 10)
                    ),
                    "heading": float(
                        row.get(column_mapping.get("heading", "heading"), 0)
                    ),
                    "ignition": row.get(
                        column_mapping.get("ignition", "ignition"), ""
                    ).lower()
                    in ["true", "1", "yes"],
                    "movement": row.get(
                        column_mapping.get("movement", "movement"), ""
                    ).lower()
                    in ["true", "1", "yes"],
                },
            }

            # Add optional fields if present
            optional_fields = [
                "battery",
                "odometer",
                "fuel_level",
                "engine_temp",
                "engine_rpm",
                "battery_voltage",
                "external_voltage",
                "gsm_signal",
            ]

            for field in optional_fields:
                if field in column_mapping and column_mapping[field] in row:
                    value = row[column_mapping[field]]
                    if value:
                        data["data"][field] = (
                            float(value) if field != "gsm_signal" else int(value)
                        )

            return data

        except Exception as e:
            raise ValueError(f"Error parsing row: {e}")

    def send_batch(self, batch):
        """Send batch of GPS data to server"""
        url = f"{self.base_url}/gps/iot/batch"
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(url, json={"updates": batch}, headers=headers)
            if response.status_code == 200:
                result = response.json()
                return result.get("status") == "success", result
            else:
                return False, {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return False, {"error": str(e)}

    def import_csv(self, csv_file, column_mapping=None):
        """Import GPS data from CSV file"""
        if not os.path.exists(csv_file):
            print(f"Error: File {csv_file} not found")
            return False

        # Default column mapping
        if column_mapping is None:
            column_mapping = {
                "imei": "imei",
                "latitude": "latitude",
                "longitude": "longitude",
                "timestamp": "timestamp",
                "speed": "speed",
                "altitude": "altitude",
                "satellites": "satellites",
                "accuracy": "accuracy",
                "heading": "heading",
                "ignition": "ignition",
                "movement": "movement",
            }

        print(f"Importing data from {csv_file}")
        print(f"Batch size: {self.batch_size}")
        print("-" * 50)

        batch = []
        row_count = 0

        with open(csv_file, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                row_count += 1

                try:
                    # Parse row to GPS data format
                    data = self.parse_csv_row(row, column_mapping)
                    batch.append(data)

                    # Send batch when full
                    if len(batch) >= self.batch_size:
                        print(f"Sending batch of {len(batch)} records...")
                        success, result = self.send_batch(batch)

                        if success:
                            self.success_count += len(batch)
                            print(f"✓ Batch sent successfully")
                        else:
                            self.error_count += len(batch)
                            self.errors.append(
                                f"Batch at row {row_count}: {result.get('error')}"
                            )
                            print(f"✗ Batch failed: {result.get('error')}")

                        batch = []

                except ValueError as e:
                    self.error_count += 1
                    self.errors.append(f"Row {row_count}: {e}")
                    print(f"✗ Skipping row {row_count}: {e}")

            # Send remaining batch
            if batch:
                print(f"Sending final batch of {len(batch)} records...")
                success, result = self.send_batch(batch)

                if success:
                    self.success_count += len(batch)
                    print(f"✓ Final batch sent successfully")
                else:
                    self.error_count += len(batch)
                    self.errors.append(f"Final batch: {result.get('error')}")
                    print(f"✗ Final batch failed: {result.get('error')}")

        # Print summary
        print("\n" + "=" * 50)
        print("Import Summary")
        print("=" * 50)
        print(f"Total rows processed: {row_count}")
        print(f"Successfully imported: {self.success_count}")
        print(f"Failed: {self.error_count}")

        if self.errors:
            print("\nErrors:")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")

        return self.error_count == 0

    def generate_sample_csv(self, output_file="sample_gps_data.csv"):
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

            # Generate sample data
            base_lat = 40.7128
            base_lon = -74.0060
            base_time = datetime.now()

            for i in range(100):
                row = {
                    "imei": "123456789012345",
                    "timestamp": base_time.isoformat(),
                    "latitude": base_lat + (i * 0.001),
                    "longitude": base_lon + (i * 0.001),
                    "speed": 30 + (i % 50),
                    "altitude": 100 + (i % 20),
                    "satellites": 8 + (i % 4),
                    "accuracy": 5 + (i % 5),
                    "heading": (i * 10) % 360,
                    "ignition": "true" if i % 10 != 0 else "false",
                    "movement": "true" if i % 10 != 0 else "false",
                    "battery": 90 - (i * 0.1),
                    "fuel_level": 80 - (i * 0.2),
                    "odometer": 10000 + (i * 0.5),
                }
                writer.writerow(row)

        print(f"✓ Sample CSV generated with 100 records")
        return output_file


def main():
    parser = argparse.ArgumentParser(description="Bulk Import GPS Tracking Data")
    parser.add_argument(
        "--url",
        default="http://localhost:8069",
        help="Odoo server URL (default: http://localhost:8069)",
    )
    parser.add_argument("--file", help="CSV file to import")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for imports (default: 100)",
    )
    parser.add_argument(
        "--generate-sample", action="store_true", help="Generate a sample CSV file"
    )
    parser.add_argument(
        "--mapping",
        type=json.loads,
        help='Column mapping as JSON (e.g., \'{"imei": "device_id"}\')',
    )

    args = parser.parse_args()

    # Create importer
    importer = BulkImporter(args.url, args.batch_size)

    if args.generate_sample:
        # Generate sample CSV
        sample_file = importer.generate_sample_csv()
        if not args.file:
            args.file = sample_file

    if args.file:
        # Import CSV file
        success = importer.import_csv(args.file, args.mapping)
        sys.exit(0 if success else 1)
    else:
        print("Error: No CSV file specified. Use --file or --generate-sample")
        sys.exit(1)


if __name__ == "__main__":
    main()
