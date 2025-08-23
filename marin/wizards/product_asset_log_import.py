import base64
import logging
import os
import re
import traceback
from csv import reader as csv_filereader
from datetime import datetime
from io import BytesIO, StringIO

from pyexcel_xls import get_data as get_sheets

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductAssetLogImport(models.TransientModel):
    _name = "product.asset.log.import"
    _description = "Import Asset Logs"

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
    vehicle_ids = fields.Many2many(comodel_name="stock.lot", string="Assets", domain="[('asset_type', '=', 'vehicle')]")
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
        if self._context.get("active_model") == "stock.lot":
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
            filter_vehicles = self.env["stock.lot"].search(domain)

        # Search for the vehicle with matching fuel card number
        for v in filter_vehicles:
            if v.fuel_card_id and fuel_card_number in v.fuel_card_id.name:
                return v

        return False

    def _clean_highway_pass_number(self, number):
        """Extracts only the numeric part from a tag string

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

    def _find_or_create_vendor(self, rfc, station_number):
        """Find or create vendor (res.partner) by RFC

        Args:
            rfc (str): RFC of the service station
            station_number (str): Station number for naming

        Returns:
            record: Found or created res.partner record, or False if RFC empty
        """
        if not rfc:
            return False

        # Clean and normalize RFC - remove hyphens and spaces
        rfc = rfc.strip().upper().replace("-", "")

        # Search for existing partner with this RFC
        existing_partner = self.env["res.partner"].search(
            [("vat", "=", rfc), ("supplier", "=", True)], limit=1
        )

        if existing_partner:
            return existing_partner

        # Create new partner
        partner_vals = {
            "name": station_number,
            "vat": rfc,
            "is_company": True,
            "supplier": True,
            "country_id": self.env.ref("base.mx"),
        }

        try:
            return self.env["res.partner"].create(partner_vals)
        except Exception as e:
            _logger.warning(f"Failed to create vendor with RFC {rfc}: {str(e)}")
            return False

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
            # If no filter, search all assets with highway pass
            domain = [("highway_pass_id", "!=", False), ("asset_type", "=", "vehicle")]
            filter_vehicles = self.env["stock.lot"].search(domain)

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
            tuple: (list of product.asset.log values, list of error messages)
        """
        asset_log = self.env["product.asset.log"]
        fuel_category = self.env.ref("marin.product_category_fuel")
        fuel_debit_product = self.env.ref("marin.product_product_fuel_debit")
        fuel_credit_product = self.env.ref("marin.product_product_fuel_credit")
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
                "Estacion",
                "Estacion RFC",
            ]
            header = sheet[6]  # 7th row (0-indexed)

            column_map = {
                col: idx for idx, col in enumerate(header) if col in required_columns
            }
            if len(column_map) != len(required_columns):
                missing = set(required_columns) - set(column_map.keys())
                raise UserError(self.env._("Missing columns: %s", ", ".join(missing)))

            # Define the vehicles to update their logs
            filter_vehicles = self.vehicle_ids or self.env["stock.lot"].search(
                [("fuel_card_id", "!=", False), ("asset_type", "=", "vehicle")]
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

                    # Extract RFC and station info for vendor mapping
                    station_rfc = (
                        str(row[column_map["Estacion RFC"]]).strip()
                        if row[column_map["Estacion RFC"]]
                        else ""
                    )
                    station_name = (
                        str(row[column_map["Estacion"]]).strip()
                        if row[column_map["Estacion"]]
                        else ""
                    )

                    # Find or create vendor
                    vendor = self._find_or_create_vendor(station_rfc, station_name)
                    amount = (
                        float(row[column_map["Cargo"]])
                        if row[column_map["Cargo"]]
                        else 0
                    ) - (
                        float(row[column_map["Abono"]])
                        if row[column_map["Abono"]]
                        else 0
                    )
                    fuel_product = (
                        fuel_credit_product if amount > 0 else fuel_debit_product
                    )
                    # Prepare log values
                    log_vals = {
                        "date": log_date,
                        "asset_id": vehicle.id,
                        "amount": amount,
                        "odometer": (
                            float(row[column_map["Km FIN"]])
                            if row[column_map["Km FIN"]]
                            else 0
                        ),
                        "state": "done",
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
                        "product_category_id": fuel_category.id,
                        "product_id": fuel_product.id,
                        "vendor_id": vendor.id if vendor else False,
                    }

                    # Check for duplicate records (done state)
                    existing_done_record = asset_log.search(
                        [
                            ("asset_id", "=", log_vals["asset_id"]),
                            ("date", "=", log_vals["date"]),
                            ("amount", "=", log_vals["amount"]),
                            ("qty_fuel", "=", log_vals["qty_fuel"]),
                            ("product_category_id", "=", fuel_category.id),
                            ("product_id", "=", fuel_product.id),
                            ("state", "=", "done"),
                        ],
                        limit=1,
                    )

                    if existing_done_record:
                        errors.append(
                            f"Row {row_idx}: Duplicate record found for vehicle with fuel card '{fuel_card_number}'"
                        )
                        continue

                    # Check for existing 'new' record from CFDI (for verification)
                    existing_new_record = asset_log.search(
                        [
                            ("asset_id", "=", log_vals["asset_id"]),
                            ("date", "=", log_vals["date"]),
                            ("qty_fuel", "=", log_vals["qty_fuel"]),
                            ("product_category_id", "=", fuel_category.id),
                            ("product_id", "=", fuel_product.id),
                            ("state", "=", "new"),
                        ],
                        limit=1,
                    )

                    if existing_new_record:
                        # Update the existing 'new' record with Effectivale data
                        # This provides verification and fills missing information
                        existing_new_record.write(
                            {
                                "amount": log_vals[
                                    "amount"
                                ],  # Update with Effectivale amount
                                "odometer": log_vals[
                                    "odometer"
                                ],  # Fill missing odometer
                                "efficiency": log_vals[
                                    "efficiency"
                                ],  # Fill missing efficiency
                                "vendor_id": log_vals[
                                    "vendor_id"
                                ],  # Fill missing vendor
                                "state": "done",  # Mark as verified/complete
                                "notes": f"{existing_new_record.notes} | Efectivale: {log_vals['notes']}",  # Combine notes
                            }
                        )
                        _logger.info(
                            "Updated CFDI record %s with Effectivale data for vehicle %s",
                            existing_new_record.id,
                            vehicle.name,
                        )
                        continue

                    logs.append(log_vals)

                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")
            return logs, errors

        except Exception as e:
            raise UserError(
                self.env._(
                    "File structure doesn't match the expected '{parser}' format.\n\n{traceback}"
                ).format(
                    parser=dict(
                        self._fields["parser"]._description_selection(self.env)
                    )[self.parser],
                    traceback=str(e),
                )
            )

    def _parse_i_d_cross(self, file_content):
        """Parse I+D highway pass transactions file in CSV format.

        Args:
            file_content (str): Base64 encoded CSV file content

        Returns:
            tuple: (list of product.asset.log values, list of error messages)
        """
        asset_log = self.env["product.asset.log"]
        highway_pass_category = self.env.ref("marin.product_category_highway_toll")
        highway_pass_debit_product = self.env.ref("marin.product_product_highway_debit")
        highway_pass_credit_product = self.env.ref(
            "marin.product_product_highway_credit"
        )
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
            filter_vehicles = self.vehicle_ids or self.env["stock.lot"].search(
                [("highway_pass_id", "!=", False), ("asset_type", "=", "vehicle")]
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
                        amount = abs(float(amount_str)) if amount_str else 0
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
                    highway_pass_product = (
                        highway_pass_credit_product
                        if amount > 0
                        else highway_pass_debit_product
                    )

                    # Prepare log values
                    log_vals = {
                        "date": log_datetime,
                        "asset_id": vehicle.id,
                        "amount": amount,
                        "state": "done",
                        "notes": notes,
                        "product_category_id": highway_pass_category.id,
                        "product_id": highway_pass_product.id,
                    }

                    # Check for duplicate records
                    existing_record = asset_log.search(
                        [
                            ("asset_id", "=", log_vals["asset_id"]),
                            ("date", "=", log_vals["date"]),
                            ("amount", "=", log_vals["amount"]),
                            ("notes", "=", log_vals["notes"]),
                            ("product_category_id", "=", highway_pass_category.id),
                            ("product_id", "=", highway_pass_product.id),
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

        except Exception:
            raise UserError(
                self.env._(
                    "File structure doesn't match the expected '{parser}' format.\n\n{traceback}"
                ).format(
                    parser=dict(
                        self._fields["parser"]._description_selection(self.env)
                    )[self.parser],
                    traceback=traceback.format_exc(),
                )
            )

    # pylint: disable=too-complex
    def _parse_i_d_recharges(self, file_content):
        """Parse I+D recharges transactions file in CSV format.

        Args:
            file_content (str): Base64 encoded CSV file content

        Returns:
            tuple: (list of product.asset.log values, list of error messages)
        """
        asset_log = self.env["product.asset.log"]
        highway_pass_category = self.env.ref("marin.product_category_highway_toll")
        highway_pass_debit_product = self.env.ref("marin.product_product_highway_debit")
        highway_pass_credit_product = self.env.ref(
            "marin.product_product_highway_credit"
        )
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
            filter_vehicles = self.vehicle_ids or self.env["stock.lot"].search(
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
                        amount = float(amount_str) * -1 if amount_str else 0
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
                    highway_pass_product = (
                        highway_pass_credit_product
                        if amount > 0
                        else highway_pass_debit_product
                    )

                    # Prepare log values
                    log_vals = {
                        "date": log_datetime,
                        "asset_id": vehicle.id,
                        "amount": amount,
                        "state": "done",
                        "notes": notes,
                        "product_category_id": highway_pass_category.id,
                        "product_id": highway_pass_product.id,
                    }

                    # Check for duplicate records
                    existing_record = asset_log.search(
                        [
                            ("asset_id", "=", log_vals["asset_id"]),
                            ("date", "=", log_vals["date"]),
                            ("amount", "=", log_vals["amount"]),
                            ("notes", "=", log_vals["notes"]),
                            ("product_category_id", "=", highway_pass_category.id),
                            ("product_id", "=", highway_pass_product.id),
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
                        self.env._("And {more_count} more errors...").format(
                            more_count=len(errors) - self.test_limit
                        )
                    )

            message = self.env._(
                "Test Mode Results:\n\n{error_count} errors were found.\n\n{error_details}"
            ).format(
                error_count=len(errors),
                error_details=(
                    "\n".join(f"  • {error}" for error in errors_messages)
                    if errors
                    else ""
                ),
            )
            raise UserError(message)

        # Create records
        try:
            with self.env.cr.savepoint():
                self.env["product.asset.log"].create(log_values_list)
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
