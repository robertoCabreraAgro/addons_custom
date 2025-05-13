import base64
import logging
import os
import re
from csv import reader as csv_filereader
from datetime import datetime
from io import BytesIO, StringIO

from pyexcel_xls import get_data as get_sheets

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FleetVehicleLogImport(models.TransientModel):
    _name = "fleet.vehicle.log.import"
    _description = "Import Vehicle Logs"

    filename = fields.Char()
    file = fields.Binary(required=True)
    parser = fields.Selection(
        [
            ("effectivale", "Effectivale"),
            ("i_d_cross", "I+D Cruces"),
            ("i_d_recharges", "I+D Recharges"),
        ],
        string="Type",
        default="effectivale",
        required=True,
    )
    vehicle_ids = fields.Many2many(comodel_name="fleet.vehicle", string="Vehicles")
    test_mode = fields.Boolean(default=True)
    test_display = fields.Selection(
        [
            ("all", "Show all"),
            ("limit", "Limited"),
        ],
        string="Display Errors",
        default="limit",
        required=True,
    )
    test_limit = fields.Integer(string="Limit", default=10)

    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Check if we are in the context of an action from the list view
        if self._context.get("active_model") == "fleet.vehicle":
            vehicle_ids = self._context.get("active_ids", [])
            # Preload IDs of selected vehicles
            res["vehicle_ids"] = [(6, 0, vehicle_ids)] if vehicle_ids else [(5, 0, 0)]

        return res

    @api.constrains("filename")
    def _check_file_extension(self):
        for record in self:
            if record.filename:
                ext = os.path.splitext(record.filename)[1].lower()
                if ext not in [".csv", ".xls", ".xlsx"]:
                    raise UserError(
                        self.env._("Only CSV, XLS, and XLSX files are allowed.")
                    )

    def _find_vehicle_by_fuel_card(self, fuel_card_number, filter_vehicles=None):
        """Find a vehicle by fuel card number

        Args:
            fuel_card_number (str): The fuel card number to search for
            filter_vehicles (recordset, optional): Filter to specific vehicles only

        Returns:
            record: The found vehicle or False
        """
        if not filter_vehicles:
            # If no filter, search all vehicles with fuel card
            domain = [("fuel_card_id", "!=", False)]
            filter_vehicles = self.env["fleet.vehicle"].search(domain)

        # Search for the vehicle with matching fuel card number
        for v in filter_vehicles:
            if v.fuel_card_id and fuel_card_number in v.fuel_card_id.name:
                return v

        return False

    def _clean_highway_pass_number(self, number):
        """
        Extracts only the numeric part from a tag string

        Args:
            tag (str): The tag string (e.g. "IMDM29081212..")

        Returns:
            str: Only the numeric part of the tag
        """
        if not number:
            return False

        # Utiliza expresión regular para extraer solo los dígitos numéricos
        numeric_part = re.sub(r"[^0-9]", "", str(number))

        if not numeric_part:
            return False

        return numeric_part

    def _find_vehicle_by_highway_pass(self, highway_pass_number, filter_vehicles=None):
        """Find a vehicle by highway pass tag number

        Args:
            highway_pass_number (str): The highway pass tag number to search for
            filter_vehicles (recordset, optional): Filter to specific vehicles only

        Returns:
            record: The found vehicle or False
        """
        highway_pass_number = self._clean_highway_pass_number(highway_pass_number)

        if not filter_vehicles:
            # If no filter, search all vehicles with highway pass
            domain = [("highway_pass_id", "!=", False)]
            filter_vehicles = self.env["fleet.vehicle"].search(domain)

        # Search for the vehicle with matching highway pass number
        for v in filter_vehicles:
            if v.highway_pass_id and highway_pass_number == v.highway_pass_name:
                return v

        return False

    def _parse_effectivale(self, file_content):
        """Parse Effectivale fuel card transactions file in XLS format.

        Args:
            file_content (str): Base64 encoded XLS file content

        Returns:
            tuple: (list of fleet.vehicle.log values, list of error messages)
        """
        fleet_vehicle_log = self.env["fleet.vehicle.log"]

        try:
            # Decode and load the Excel file
            file_data = base64.b64decode(file_content)
            sheets = get_sheets(BytesIO(file_data))
            sheet = sheets[list(sheets.keys())[0]]  # Get first sheet

            # Validate required columns
            required_columns = [
                "Cuenta",
                "Fecha",
                "Cargo",
                "Abono",
                "Km FIN",
                "Concepto",
                "Litros",
                "Rendimiento",
            ]
            header = sheet[6]  # 7th row (0-indexed)

            column_map = {
                col: idx for idx, col in enumerate(header) if col in required_columns
            }
            if len(column_map) != len(required_columns):
                missing = set(required_columns) - set(column_map.keys())
                raise UserError(self.env._("Missing columns: %s", ", ".join(missing)))

            # Define the vehicles to update their logs
            filter_vehicles = self.vehicle_ids or self.env["fleet.vehicle"].search(
                [("fuel_card_id", "!=", False)]
            )

            logs = []
            errors = []
            for row_idx, row in enumerate(sheet[7:], 8):  # Start from row 8
                if not row:  # skip empty rows
                    continue

                try:
                    # Get the account number from the row
                    fuel_card_number = (
                        str(row[column_map["Cuenta"]])
                        if row[column_map["Cuenta"]]
                        else False
                    )

                    if not fuel_card_number:
                        errors.append(f"Row {row_idx}: Missing fuel card number")
                        continue  # Skip empty rows

                    # Parse ISO datetime (format: '2025-04-02 15:38:18')
                    date_str = str(row[column_map["Fecha"]]).strip()
                    try:
                        log_date = datetime.strptime(
                            date_str, "%Y-%m-%d %H:%M:%S"
                        ).date()
                    except ValueError:
                        errors.append(
                            f"Row {row_idx}: Invalid date format '{date_str}'"
                        )
                        continue

                    # Validate vehicle
                    vehicle = self._find_vehicle_by_fuel_card(
                        fuel_card_number, filter_vehicles
                    )
                    if not vehicle:
                        error_msg = f"Row {row_idx}: No vehicle found with fuel card '{row[column_map['Cuenta']]}'"
                        errors.append(error_msg)
                        continue

                    # Prepare log values
                    log_vals = {
                        "date": log_date,
                        "vehicle_id": vehicle.id,
                        "amount": (
                            float(row[column_map["Abono"]])
                            if row[column_map["Abono"]]
                            else 0
                        )
                        - (
                            float(row[column_map["Cargo"]])
                            if row[column_map["Cargo"]]
                            else 0
                        ),
                        "odometer": (
                            float(row[column_map["Km FIN"]])
                            if row[column_map["Km FIN"]]
                            else 0
                        ),
                        "notes": row[column_map["Concepto"]],
                        "qty_fuel": (
                            float(row[column_map["Litros"]])
                            if row[column_map["Litros"]]
                            else 0
                        ),
                        "efficiency": (
                            float(row[column_map["Rendimiento"]])
                            if row[column_map["Rendimiento"]]
                            else 0
                        ),
                        "type": "fuel",
                    }

                    # Check for duplicate records
                    existing_record = fleet_vehicle_log.search(
                        [
                            ("vehicle_id", "=", log_vals["vehicle_id"]),
                            ("date", "=", log_vals["date"]),
                            ("amount", "=", log_vals["amount"]),
                            ("qty_fuel", "=", log_vals["qty_fuel"]),
                        ],
                        limit=1,
                    )

                    if existing_record:
                        errors.append(
                            f"Row {row_idx}: Duplicate record found for vehicle with fuel card '{fuel_card_number}'"
                        )
                        continue

                    logs.append(log_vals)

                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")
            return logs, errors

        except Exception as e:
            raise UserError(
                self.env._(
                    "File structure doesn't match the expected '%(parser)s' format.\n\n%(traceback)s"
                )
                % {
                    "parser": dict(
                        self._fields["parser"]._description_selection(self.env)
                    )[self.parser],
                    "traceback": str(e),
                }
            )

    def _parse_i_d_cross(self, file_content):
        """Parse I+D highway pass transactions file in CSV format.

        Args:
            file_content (str): Base64 encoded CSV file content

        Returns:
            tuple: (list of fleet.vehicle.log values, list of error messages)
        """
        fleet_vehicle_log = self.env["fleet.vehicle.log"]

        try:
            # Decode and load the CSV file
            file_data = base64.b64decode(file_content)

            csv_file = StringIO(file_data.decode("utf-8"))
            csv_reader = csv_filereader(csv_file, delimiter=",")

            # Get header (first line)
            header = next(csv_reader, [])

            # Validate required columns
            required_columns = [
                "Tag",
                "Importe",
                "Fecha Aplicacion",
                "Hora Aplicacion",
                "Caseta",
                "Clase",
                "Consecar",
            ]

            column_map = {
                col: idx for idx, col in enumerate(header) if col in required_columns
            }
            if len(column_map) != len(required_columns):
                missing = set(required_columns) - set(column_map.keys())
                raise UserError(self.env._("Missing columns: %s", ", ".join(missing)))

            # Define the vehicles to update their logs
            filter_vehicles = self.vehicle_ids or self.env["fleet.vehicle"].search(
                [("highway_pass_id", "!=", False)]
            )

            logs = []
            errors = []
            for row_idx, row in enumerate(csv_reader, 2):  # Start from row 2
                if not row or len(row) < len(header):  # skip empty/incomplete rows
                    continue

                try:
                    # Get the tag number from the row
                    tag_number = (
                        str(row[column_map["Tag"]])
                        if column_map.get("Tag") < len(row)
                        else False
                    )

                    if not tag_number:
                        errors.append(f"Row {row_idx}: Missing highway pass number")
                        continue

                    # Parse datetime (format: 'YYYY-MM-DD' + 'HH:MM:SS')
                    date_str = str(row[column_map["Fecha Aplicacion"]]).strip()
                    time_str = str(row[column_map["Hora Aplicacion"]]).strip()

                    try:
                        # Combine date and time
                        log_datetime = datetime.strptime(
                            f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S"
                        )
                    except ValueError:
                        errors.append(
                            f"Row {row_idx}: Invalid date/time format '{date_str} {time_str}'"
                        )
                        continue

                    # Validate vehicle
                    vehicle = self._find_vehicle_by_highway_pass(
                        tag_number, filter_vehicles
                    )
                    if not vehicle:
                        error_msg = f"Row {row_idx}: No vehicle found with highway pass number '{tag_number}'"
                        errors.append(error_msg)
                        continue

                    # Get amount and convert to negative
                    try:
                        amount_str = (
                            row[column_map["Importe"]]
                            if column_map.get("Importe") < len(row)
                            else "0"
                        )
                        # Remove currency symbols and thousand separators
                        amount_str = re.sub(r"[^\d.-]", "", amount_str)
                        amount = -abs(float(amount_str)) if amount_str else 0
                    except ValueError:
                        errors.append(
                            f"Row {row_idx}: Invalid amount format '{row[column_map['Importe']]}'"
                        )
                        continue

                    # Prepare notes as concatenation of various fields
                    caseta = (
                        row[column_map["Caseta"]]
                        if column_map.get("Caseta") < len(row)
                        else ""
                    )
                    saldo = (
                        row[column_map["Clase"]]
                        if column_map.get("Clase") < len(row)
                        else ""
                    )
                    consecar = (
                        row[column_map["Consecar"]]
                        if column_map.get("Consecar") < len(row)
                        else ""
                    )

                    notes = f"Caseta: {caseta}, Clase: {saldo}, Consecar: {consecar}"

                    # Prepare log values
                    log_vals = {
                        "date": log_datetime,
                        "vehicle_id": vehicle.id,
                        "amount": amount,
                        "state": "done",
                        "notes": notes,
                        "type": "highway_pass",
                    }

                    # Check for duplicate records
                    existing_record = fleet_vehicle_log.search(
                        [
                            ("vehicle_id", "=", log_vals["vehicle_id"]),
                            ("date", "=", log_vals["date"]),
                            ("amount", "=", log_vals["amount"]),
                            ("notes", "=", log_vals["notes"]),
                            ("type", "=", "highway_pass"),
                        ],
                        limit=1,
                    )

                    if existing_record:
                        errors.append(
                            f"Row {row_idx}: Duplicate record found for vehicle with highway pass number '{tag_number}'"
                        )
                        continue

                    logs.append(log_vals)

                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")

            return logs, errors

        except Exception as e:
            import traceback

            raise UserError(
                self.env._(
                    "File structure doesn't match the expected '%(parser)s' format.\n\n%(traceback)s"
                )
                % {
                    "parser": dict(
                        self._fields["parser"]._description_selection(self.env)
                    )[self.parser],
                    "traceback": str(e) + "\n" + traceback.format_exc(),
                }
            )

    def _parse_i_d_recharges(self, file_content):
        """Parse I+D recharges transactions file in CSV format.

        Args:
            file_content (str): Base64 encoded CSV file content

        Returns:
            tuple: (list of fleet.vehicle.log values, list of error messages)
        """
        fleet_vehicle_log = self.env["fleet.vehicle.log"]

        try:
            # Decode and load the CSV file
            file_data = base64.b64decode(file_content)

            csv_file = StringIO(file_data.decode("utf-8"))
            csv_reader = csv_filereader(csv_file, delimiter=",")

            # Get header (first line)
            header = next(csv_reader, [])

            # Validate required columns
            required_columns = [
                "Fecha",
                "Hora",
                "Movimiento",
                "Folio",
                "Referencia",
                "Importe",
            ]

            column_map = {
                col: idx for idx, col in enumerate(header) if col in required_columns
            }
            if len(column_map) != len(required_columns):
                missing = set(required_columns) - set(column_map.keys())
                raise UserError(self.env._("Missing columns: %s", ", ".join(missing)))

            # Define the vehicles to update their logs
            filter_vehicles = self.vehicle_ids or self.env["fleet.vehicle"].search(
                [("highway_pass_name", "!=", False)]
            )

            logs = []
            errors = []

            for row_idx, row in enumerate(csv_reader, 2):  # Start from row 2
                if not row or len(row) < len(header):  # skip empty/incomplete rows
                    continue

                try:
                    # Check if the movement contains the word "RECARGA"
                    movement = (
                        row[column_map["Movimiento"]]
                        if column_map.get("Movimiento") < len(row)
                        else ""
                    )

                    # Verify if the movement contains "RECARGA"
                    if "RECARGA" not in movement.upper():
                        errors.append(
                            f"Row {row_idx}: Movement '{movement}' does not contain 'RECARGA'"
                        )
                        continue

                    # Get the reference number from the row
                    reference = (
                        str(row[column_map["Referencia"]])
                        if column_map.get("Referencia") < len(row)
                        else False
                    )

                    # Skip rows with empty Referencia o Importe
                    if not reference:
                        errors.append(f"Row {row_idx}: Missing reference")
                        continue

                    importe_str = (
                        row[column_map["Importe"]]
                        if column_map.get("Importe") < len(row)
                        else ""
                    )
                    if not importe_str:
                        errors.append(f"Row {row_idx}: Missing amount")
                        continue

                    # Parse datetime (format: 'DD/MM/YYYY' + 'HH:MM:SS')
                    date_str = str(row[column_map["Fecha"]]).strip()
                    time_str = str(row[column_map["Hora"]]).strip()

                    try:
                        # Combine date and time (sometimes time came without seconds)
                        datetime_format = (
                            "%d/%m/%Y %H:%M"
                            if len(time_str) < 6
                            else "%d/%m/%Y %H:%M:%S"
                        )
                        log_datetime = datetime.strptime(
                            f"{date_str} {time_str}", datetime_format
                        )
                    except ValueError:
                        errors.append(
                            f"Row {row_idx}: Invalid date/time format '{date_str} {time_str}'"
                        )
                        continue

                    # Validate vehicle
                    vehicle = self._find_vehicle_by_highway_pass(
                        reference, filter_vehicles
                    )
                    if not vehicle:
                        error_msg = f"Row {row_idx}: No vehicle found with reference '{reference}'"
                        errors.append(error_msg)
                        continue

                    # Get amount and convert to value
                    try:
                        # Remove currency symbols and thousand separators
                        amount_str = re.sub(r"[^\d.-]", "", importe_str)
                        amount = float(amount_str) if amount_str else 0
                    except ValueError:
                        errors.append(
                            f"Row {row_idx}: Invalid amount format '{importe_str}'"
                        )
                        continue

                    # Prepare notes as concatenation of various fields
                    movement = (
                        row[column_map["Movimiento"]]
                        if column_map.get("Movimiento") < len(row)
                        else ""
                    )
                    folio = (
                        row[column_map["Folio"]]
                        if column_map.get("Folio") < len(row)
                        else ""
                    )

                    notes = f"Movimiento: {movement}, Folio: {folio}"

                    # Prepare log values
                    log_vals = {
                        "date": log_datetime,
                        "vehicle_id": vehicle.id,
                        "amount": amount,
                        "state": "done",
                        "notes": notes,
                        "type": "highway_pass",
                    }

                    # Check for duplicate records
                    existing_record = fleet_vehicle_log.search(
                        [
                            ("vehicle_id", "=", log_vals["vehicle_id"]),
                            ("date", "=", log_vals["date"]),
                            ("amount", "=", log_vals["amount"]),
                            ("notes", "=", log_vals["notes"]),
                            ("type", "=", "highway_pass"),
                        ],
                        limit=1,
                    )

                    if existing_record:
                        errors.append(
                            f"Row {row_idx}: Duplicate record found for vehicle with reference '{reference}'"
                        )
                        continue

                    logs.append(log_vals)

                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")

            return logs, errors

        except Exception as e:
            import traceback

            raise UserError(
                self.env._(
                    "File structure doesn't match the expected '%(parser)s' format.\n\n%(traceback)s",
                    {
                        "parser": dict(
                            self._fields["parser"]._description_selection(self.env)
                        )[self.parser],
                        "traceback": str(e) + "\n" + traceback.format_exc(),
                    },
                )
            )

    def action_import(self):
        """Import vehicle logs based on the selected parser"""
        self.ensure_one()

        if not self.file:
            raise UserError(self.env._("Please select a file to import."))

        # Dynamic parser selection
        parser_name = f"_parse_{self.parser}"
        if not hasattr(self, parser_name):
            raise UserError(
                self.env._("Selected parser '%s' is not implemented.", self.parser)
            )

        log_values_list, errors = getattr(self, parser_name)(self.file)

        # Show errors without creating records
        if self.test_mode:
            errors_messages = errors
            if self.test_display == "limit":
                errors_messages = errors[: self.test_limit]
                if len(errors) > self.test_limit:
                    errors_messages.append(
                        self.env._("And %(more_count)s more errors...")
                        % {"more_count": len(errors) - self.test_limit}
                    )

            message = self.env._(
                "Test Mode Results:\n\n%(error_count)s errors were found.\n\n%(error_details)s"
            ) % {
                "error_count": len(errors),
                "error_details": (
                    "\n".join(f"  • {error}" for error in errors_messages)
                    if errors
                    else ""
                ),
            }
            raise UserError(message)

        # Create records
        try:
            with self.env.cr.savepoint():
                self.env["fleet.vehicle.log"].create(log_values_list)
        except Exception as e:
            raise UserError(self.env._("Error creating logs: %s", str(e)))

        # Success notification
        message = self.env._(
            "Successfully imported %(imported_count)s logs with %(errors_count)s errors ignored",
            imported_count=len(log_values_list),
            errors_count=len(errors),
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Import Result"),
                "message": message,
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
