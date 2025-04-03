# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError
import xlrd
import re
import base64
import logging
import chardet

from datetime import datetime

_logger = logging.getLogger(__name__)

BBVA_TXT_HEADER = ["Día", "Concepto / Referencia", "cargo", "Abono", "Saldo"]

BBVA_XLSX_HEADER = [
    "FECHA",
    "DESCRIPCIÓN",
    "ABONO",
    "CARGO",
    "SALDO",
]


class BBVAParser(models.AbstractModel):
    _name = "bbva.parser"
    _description = "BBVA files parser"

    def _decode_file_content(self, data_file):
        """
        Detects the encoding of a file and decodes it into readable text.

        If the detected encoding is "ISO-8859-1", it is converted to "UTF-8".
        The decoded content is split into lines for further processing.

        :param data_file: Bytes object representing the file content.
        :return: List of decoded lines.
        """
        # Detect encoding
        encoding_detected = chardet.detect(data_file)["encoding"]

        # Normalize encoding
        if encoding_detected and encoding_detected.lower() == "iso-8859-1":
            encoding_detected = "utf-8"

        # Decode content and split into lines
        lines = data_file.decode(encoding_detected, errors="replace").splitlines()

        return lines

    def _validate_header(self, data_file, file_type):
        """Validates if the file header matches the expected format based on file type.

        :param data_file: Data file in bytes
        :param file_type: Type of file ('txt' or 'xlsx')
        :return: True if the header is valid, False otherwise
        """
        try:
            if file_type == "txt":
                # Decode file and convert it into lines
                lines = self._decode_file_content(data_file)

                if not lines:
                    return False

                header = lines[0].strip().split("\t")
                return header == BBVA_TXT_HEADER

            elif file_type == "xlsx":
                header_row = 5
                workbook = xlrd.open_workbook(file_contents=data_file)
                sheet = workbook.sheet_by_index(0)

                if sheet.nrows <= header_row:
                    return False

                header = [
                    sheet.cell(header_row, col).value.strip()
                    for col in range(sheet.ncols)
                ]
                return header == BBVA_XLSX_HEADER

            return False

        except Exception as e:
            _logger.error("Error validating %s header: %s", file_type, str(e))
            return False

    def _generate_unique_import_id(
        self, journal_code, transaction_date, sequence, padding=4
    ):
        """
        Generates a universal unique import ID with standardized format.

        Format: {JOURNAL_CODE}-{YYMM}-{SEQ}

        Args:
            journal_code (str): Journal's short code (e.g., 'BNK-BBVA')
            transaction_date (date): Date object or date string (YYYY-MM-DD)
            sequence (int): Transaction sequence number
            padding (int): Zero-padding length for sequence (default: 4)

        Returns:
            str: Formatted unique import ID (e.g., 'BNK-BBVA-2403-0042')
        """
        try:
            # Ensure journal code is clean (no special chars)
            clean_journal_code = re.sub(r"[^A-Z0-9-]", "", journal_code.upper().strip())

            # Parse date (handles both string and date object)
            if isinstance(transaction_date, str):
                dt = fields.Date.from_string(transaction_date)
            else:
                dt = transaction_date

            # Format components
            yymm = dt.strftime("%y%m")  # Last 2 digits of year + 2-digit month
            seq_str = str(sequence).zfill(padding)  # Zero-padded sequence

            return f"{clean_journal_code}-{yymm}-{seq_str}"

        except Exception as e:
            raise ValueError(
                _("Failed to generate transaction ID. Please check input parameters.")
            )

    def _parse_date(self, date_str, date_format):
        """Parse date from string using specified format.

        Args:
            date_str (str): Date string
            date_format (str): Format string for datetime.strptime

        Returns:
            str: Date string in Odoo format

        Raises:
            UserError: If date format is invalid
        """
        try:
            date_obj = datetime.strptime(date_str, date_format)
            return fields.Date.to_string(date_obj)
        except ValueError:
            raise UserError(
                _("Invalid date format: %s. Expected format: %s")
                % (date_str, date_format)
            )

    def _find_partner_bank(self, reference):
        """Try to find partner based on reference (description).

        Args:
            reference (str): Transaction reference/description

        Returns:
            res.partner.bank: Partner bank record if found, empty recordset otherwise
        """
        bank_acc_obj = self.env["res.partner.bank"]

        # Buscar números de cuenta en la referencia
        account_numbers = re.findall(r"\b\d{10,20}\b", reference)
        for acc_num in account_numbers:
            bank_account = bank_acc_obj.search(
                [("acc_number", "ilike", acc_num)], limit=1
            )
            if bank_account:
                return bank_account

        return bank_acc_obj

    def _validate_date_range(self, date_start, date_end):
        """Validate that dates are from the same month and year.

        Args:
            date_start (str): Start date in Odoo format
            date_end (str): End date in Odoo format

        Raises:
            UserError: If dates are from different months or years
        """

        if not date_start or not date_end:
            raise UserError(_("No valid transactions found in the file"))

        start_date = fields.Date.to_date(date_start)
        end_date = fields.Date.to_date(date_end)

        if start_date.year != end_date.year or start_date.month != end_date.month:
            raise UserError(
                _(
                    "All transactions must be from the same month and year. "
                    "Start date: %(start)s, End date: %(end)s"
                )
                % {"start": start_date, "end": end_date}
            )

    def parse_bbva_file(self, data_file, journal, file_type):
        """Parse BBVA file (TXT or XLSX format).

        Args:
            data_file (bytes): The file content to parse
            journal (account.journal): Journal record
            file_type (str): File type ('txt' or 'xlsx')

        Returns:
            dict: Contains statement name, date, and transactions

        Raises:
            UserError: If file format is invalid or contains inconsistent data
        """
        if not self._validate_header(data_file, file_type):
            raise UserError(
                _("Invalid file format: Header does not match expected BBVA format")
            )

        try:
            if file_type == "txt":
                return self._parse_txt_file(data_file, journal)
            elif file_type == "xlsx":
                return self._parse_xlsx_file(data_file, journal)
            else:
                raise UserError(
                    _("Unsupported file type. Only TXT and XLSX formats are supported.")
                )

        except UnicodeDecodeError:
            raise UserError(_("Encoding error: Could not decode the file content"))
        except Exception as e:
            raise UserError(_("File processing error:\n\t- %s") % str(e))

    def _parse_txt_file(self, data_file, journal):
        """Parse BBVA TXT file format.

        Args:
            data_file (bytes): The file content to parse
            journal (account.journal): Journal record

        Returns:
            dict: Contains statement name, date, and transactions
        """
        # Decode file and convert it into lines
        lines = self._decode_file_content(data_file)

        if not lines:
            raise UserError(_("Empty file: The uploaded file contains no data"))

        transactions = []
        date_start = None
        date_end = None
        sequence = 1
        lines_number = len(lines)
        for line in reversed(lines[1:]):
            # Skip empty lines
            if not line.strip():
                continue

            # Validate and process each line
            values = line.strip().split("\t")
            if len(values) != 5:
                raise UserError(
                    _("Line %d: Invalid format, expected 5 columns")
                    % (lines_number - sequence)
                )

            # Get cell values
            try:
                day_str = values[0].strip()
                date = self._parse_date(day_str, "%d-%m-%Y")
                reference = values[1].strip()
                debit = float(values[2].replace(",", "").strip() or "0")
                credit = float(values[3].replace(",", "").strip() or "0")
            except (ValueError, IndexError) as e:
                raise UserError(
                    _("Line %d: Invalid data format - %s")
                    % ((lines_number - sequence), str(e))
                )

            # Validate required values
            if not (debit or credit):
                raise UserError(
                    _("Line %d: Transaction must have either debit or credit amount")
                    % (lines_number - sequence)
                )

            # Set start/end dates
            if date_end is None:
                date_end = date
            date_start = date  # Always updates with last valid date

            # Create transaction
            partner_bank = self._find_partner_bank(reference)
            transactions.append(
                {
                    "date": date,
                    "payment_ref": reference,
                    "amount": credit - debit,
                    "account_number": partner_bank.acc_number if partner_bank else None,
                    "partner_id": partner_bank.partner_id.id,
                    "sequence": sequence,
                    "unique_import_id": self._generate_unique_import_id(
                        journal.code, date, sequence
                    ),
                }
            )

            # Update sequence
            sequence += 1

        # Final validations
        self._validate_date_range(date_start, date_end)

        # Create statement data
        statement_name = fields.Date.from_string(date_start).strftime("%y-%m")
        return {
            "name": statement_name,  # YY-MM format from start date
            "date": date_end,  # Using last transaction date as statement date
            "transactions": transactions,
        }

    def _parse_xlsx_file(self, data_file, journal):
        """Parse BBVA XLSX file format.

        Args:
            data_file (bytes): The Excel file content to parse
            journal (account.journal): Journal record

        Returns:
            dict: Contains statement name, date, and transactions
        """
        try:
            workbook = xlrd.open_workbook(file_contents=data_file)
            sheet = workbook.sheet_by_index(0)
            header_row = 5  # Header is in row 5

            if sheet.nrows <= header_row + 1:  # Header row + at least 1 data row
                raise UserError(
                    _("Empty file: The Excel file contains no transaction data")
                )

            transactions = []
            date_start = None
            date_end = None
            sequence = 1
            footer_row = sheet.nrows - 1

            for row_number in reversed(range(header_row + 1, sheet.nrows)):

                # Skip empty rows
                if not any(
                    sheet.cell(row_number, col).value for col in range(sheet.ncols)
                ):
                    continue

                # Skip footer
                if row_number == footer_row:
                    continue

                # Get cell values
                try:
                    date_value = sheet.cell(row_number, 0).value
                    date = self._parse_date(date_value, "%Y-%m-%d")
                    reference = str(sheet.cell(row_number, 1).value).strip()
                    credit = float(sheet.cell(row_number, 2).value or 0)
                    debit = float(sheet.cell(row_number, 3).value or 0)
                except (ValueError, IndexError) as e:
                    raise UserError(
                        _("Row %d: Invalid data format - %s") % (row_number + 1, str(e))
                    )

                # Validate required values
                if not (debit or credit):
                    raise UserError(
                        _("Row %d: Transaction must have either debit or credit amount")
                        % (row_number + 1)
                    )

                # Set start/end dates
                if date_end is None:
                    date_end = date
                date_start = date

                # Create transaction
                partner_bank = self._find_partner_bank(reference)
                transactions.append(
                    {
                        "date": date,
                        "payment_ref": reference,
                        "amount": credit - debit,
                        "account_number": partner_bank.acc_number
                        if partner_bank
                        else None,
                        "partner_id": partner_bank.partner_id.id
                        if partner_bank.partner_id
                        else None,
                        "sequence": sequence,
                        "unique_import_id": self._generate_unique_import_id(
                            journal.code, date, sequence
                        ),
                    }
                )

                # Update sequence
                sequence += 1

            # Final validations
            self._validate_date_range(date_start, date_end)

            # Create statement data
            statement_name = fields.Date.from_string(date_start).strftime("%y-%m")
            return {
                "name": statement_name,  # YY-MM format from start date
                "date": date_end,  # Using last transaction date as statement date
                "transactions": transactions,
            }

        except xlrd.XLRDError as e:
            raise UserError(_("Excel file error: %s") % str(e))
