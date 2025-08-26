from datetime import datetime, timedelta
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockLotRule(models.Model):
    _name = "stock.lot.rule"
    _description = "Stock Lot Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
        help="Name of the lot rule schema",
    )

    format_pattern = fields.Char(
        string="Format Pattern",
        required=True,
        default="%(yy)s%(mm)s-%(product_id)s",
        tracking=True,
        help="Format pattern for lot naming. Available placeholders:\n"
        "%(yy)s: 2-digit year\n"
        "%(yyyy)s: 4-digit year\n"
        "%(mm)s: 2-digit month\n"
        "%(dd)s: 2-digit day\n"
        "%(product_code)s: Product code placeholder\n"
        "%(product_id)s: Product ID placeholder\n"
        "%(ref)s: Vendor lot number field placeholder\n"
        "Example: '%(yy)s%(mm)s%(dd)s|%(product_id)s - %(ref)s' creates '250315|12345 - AYE5AT009A'",
    )

    expiration_time = fields.Integer(
        string="Expiration Date",
        default=0,
        tracking=True,
        help="Number of days after the receipt of the products (from the vendor"
        " or in stock after production) after which the goods may become dangerous"
        " and must not be consumed. It will be computed on the lot/serial number.",
    )

    use_time = fields.Integer(
        string="Best Before Date",
        default=0,
        tracking=True,
        help="Number of days before the Expiration Date after which the goods starts"
        " deteriorating, without being dangerous yet. It will be computed on the lot/serial number.",
    )

    removal_time = fields.Integer(
        string="Removal Date",
        default=0,
        tracking=True,
        help="Number of days before the Expiration Date after which the goods"
        " should be removed from the stock. It will be computed on the lot/serial number.",
    )

    alert_time = fields.Integer(
        string="Alert Date",
        default=0,
        tracking=True,
        help="Number of days before the Expiration Date after which an alert should be"
        " raised on the lot/serial number. It will be computed on the lot/serial number.",
    )

    active = fields.Boolean(string="Active", default=True, tracking=True)

    # Computed fields for statistics
    product_count = fields.Integer(
        string="Products Using This Rule",
        compute="_compute_product_count",
        help="Number of products that use this lot rule",
    )

    @api.constrains("expiration_time", "use_time", "removal_time", "alert_time")
    def _check_days_positive(self):
        """Validate that days are positive integers"""
        for record in self:
            if any(
                days < 0
                for days in [
                    record.expiration_time,
                    record.use_time,
                    record.removal_time,
                    record.alert_time,
                ]
            ):
                raise ValidationError(_("Days must be positive integers"))

    @api.constrains("format_pattern")
    def _check_format_pattern(self):
        """Validate format pattern"""
        for record in self:
            if not record.format_pattern:
                raise ValidationError(_("Format pattern cannot be empty"))

            # Check if pattern contains at least one date placeholder
            date_placeholders = ["%(yy)s", "%(yyyy)s", "%(mm)s", "%(dd)s"]
            has_date = any(
                placeholder in record.format_pattern
                for placeholder in date_placeholders
            )

            if not has_date:
                raise ValidationError(
                    _("Format pattern must contain at least one date placeholder: %s")
                    % ", ".join(date_placeholders)
                )

            # Check if pattern contains product placeholder (optional for simple date-only formats)
            has_product_placeholder = (
                "%(product_code)s" in record.format_pattern
                or "%(product_id)s" in record.format_pattern
                or "%(ref)s" in record.format_pattern
            )
            # Only require product placeholder if pattern seems to need it (contains separators)
            pattern_has_separators = any(
                sep in record.format_pattern for sep in ["-", " - ", "_", ".", "|"]
            )
            if pattern_has_separators and not has_product_placeholder:
                raise ValidationError(
                    _(
                        "Format pattern with separators should contain %(product_code)s, %(product_id)s or %(ref)s placeholder"
                    )
                )

            # Try to validate the pattern by doing a test format
            try:
                test_data = {
                    "yy": "25",
                    "yyyy": "2025",
                    "mm": "02",
                    "dd": "15",
                    "product_code": "TEST",
                    "product_id": "12345",
                    "ref": "REF123",
                }
                # Only test with required placeholders
                required_placeholders = [
                    "yy",
                    "yyyy",
                    "mm",
                    "dd",
                    "product_code",
                    "product_id",
                    "ref",
                ]
                test_format_data = {}
                for placeholder in required_placeholders:
                    if f"%({placeholder})s" in record.format_pattern:
                        test_format_data[placeholder] = test_data[placeholder]

                record.format_pattern % test_format_data
            except (KeyError, ValueError, TypeError) as e:
                raise ValidationError(_("Invalid format pattern: %s") % str(e))

    def _get_manufacture_date(self, lot_name):
        """
        Extract manufacturing date from lot name based on format pattern.

        Args:
            lot_name (str): Name of the lot

        Returns:
            datetime: Manufacturing date or None if parsing fails

        Raises:
            ValidationError: If lot name format is invalid or date extraction fails
        """
        if not lot_name:
            return None

        try:
            # Create regex pattern from format pattern
            pattern_regex = self._create_regex_from_pattern()

            # Match the lot name against the pattern
            match = re.match(pattern_regex, lot_name)
            if not match:
                raise ValidationError(
                    _("Lot name '%s' doesn't match the expected format pattern: %s")
                    % (lot_name, self.format_pattern)
                )

            # Extract date components from the match
            date_info = match.groupdict()

            # Get year
            year = None
            if "yyyy" in date_info:
                year = int(date_info["yyyy"])
            elif "yy" in date_info:
                yy = int(date_info["yy"])
                # Convert 2-digit year to 4-digit year
                # Assume years 00-30 are 2000-2030, 31-99 are 1931-1999
                if yy <= 30:
                    year = 2000 + yy
                else:
                    year = 1900 + yy

            if not year:
                raise ValidationError(
                    _("Could not extract year from lot name '%s'") % lot_name
                )

            # Get month
            month = 1  # Default to January if no month specified
            if "mm" in date_info:
                month = int(date_info["mm"])
                if month < 1 or month > 12:
                    raise ValidationError(
                        _(
                            "Invalid month in lot name '%s'. Month must be between 01 and 12"
                        )
                        % lot_name
                    )

            # Get day
            day = 1  # Default to first day of month if no day specified
            if "dd" in date_info:
                day = int(date_info["dd"])
                if day < 1 or day > 31:
                    raise ValidationError(
                        _("Invalid day in lot name '%s'. Day must be between 01 and 31")
                        % lot_name
                    )

            # Create manufacturing date
            manufacture_date = datetime(year, month, day)

            # Validate that manufacturing date is not in the future
            if manufacture_date > datetime.now():
                raise ValidationError(
                    _("Manufacturing date cannot be in the future. " "Parsed date: %s")
                    % manufacture_date.strftime("%Y-%m-%d")
                )

            return manufacture_date

        except (ValueError, TypeError, re.error) as e:
            raise ValidationError(
                _("Error parsing lot name '%s': %s") % (lot_name, str(e))
            )

    def _create_regex_from_pattern(self):
        """
        Create a regex pattern from the format pattern.

        Returns:
            str: Regex pattern string
        """
        # Start with the format pattern
        regex_pattern = self.format_pattern

        # Replace placeholders with named regex groups
        replacements = {
            "%(yyyy)s": r"(?P<yyyy>\d{4})",
            "%(yy)s": r"(?P<yy>\d{2})",
            "%(mm)s": r"(?P<mm>\d{2})",
            "%(dd)s": r"(?P<dd>\d{2})",
            "%(product_code)s": r"(?P<product_code>.*?)",
            "%(product_id)s": r"(?P<product_id>\d+)",
            "%(ref)s": r"(?P<ref>.*?)",
        }

        # Escape special regex characters first
        regex_pattern = re.escape(regex_pattern)

        # Then replace our placeholders
        for placeholder, regex_group in replacements.items():
            escaped_placeholder = re.escape(placeholder)
            regex_pattern = regex_pattern.replace(escaped_placeholder, regex_group)

        # Make it match the entire string
        regex_pattern = "^" + regex_pattern + "$"

        return regex_pattern

    def _get_expiration_date(self, manufacture_date):
        """
        Get expiration date from manufacturing date.

        Args:
            manufacture_date (datetime): Manufacturing date

        Returns:
            datetime: Expiration date
        """
        if not manufacture_date or not self.expiration_time:
            return None
        return manufacture_date + timedelta(days=self.expiration_time)

    def _get_use_date(self, manufacture_date):
        """
        Get use date from manufacturing date.

        Args:
            manufacture_date (datetime): Manufacturing date

        Returns:
            datetime: Use date
        """
        if not manufacture_date or not self.use_time:
            return None
        return manufacture_date + timedelta(days=self.use_time)

    def _get_removal_date(self, manufacture_date):
        """
        Get removal date from manufacturing date.

        Args:
            manufacture_date (datetime): Manufacturing date

        Returns:
            datetime: Removal date
        """
        if not manufacture_date or not self.removal_time:
            return None
        return manufacture_date + timedelta(days=self.removal_time)

    def _get_alert_date(self, manufacture_date):
        """
        Get alert date from manufacturing date.

        Args:
            manufacture_date (datetime): Manufacturing date

        Returns:
            datetime: Alert date
        """
        if not manufacture_date or not self.alert_time:
            return None
        return manufacture_date + timedelta(days=self.alert_time)

    def _generate_lot_name(self, partial_name, product, ref_value=None):
        """
        Intelligent lot name generation using format_pattern analysis.

        Args:
            partial_name (str): Partial lot name input
            product: Product record
            ref_value (str, optional): Reference value to use for %(ref)s placeholder

        Returns:
            str: Suggested complete lot name
        """
        self.ensure_one()
        if not partial_name or not product:
            return partial_name

        # Early return if already valid
        result = self._verify_lot_name_format(
            partial_name, product_id=product.id, ref_value=ref_value
        )
        if result["valid"]:
            return partial_name

        # Extract required placeholders from format_pattern
        required_placeholders = re.findall(r"%\((\w+)\)s", self.format_pattern)

        # Try to extract existing data from partial name using partial match
        extracted_data = self._extract_partial_data(partial_name, required_placeholders)

        if not extracted_data:
            return partial_name

        # Build complete data set with defaults
        now = datetime.now()

        defaults = {
            "yy": now.strftime("%y"),
            "yyyy": now.strftime("%Y"),
            "mm": now.strftime("%m"),
            "dd": now.strftime("%d"),
            "product_code": product.default_code or "",
            "product_id": product.id,
            "ref": ref_value or "VENDOR_LOT_NUMBER",
        }

        # Build complete data: start with defaults, override with extracted data
        complete_data = {}
        for placeholder in required_placeholders:
            complete_data[placeholder] = extracted_data.get(
                placeholder
            ) or defaults.get(placeholder)
            if placeholder in ["product_id", "ref"]:
                complete_data[placeholder] = defaults.get(placeholder)

        # Try to generate the lot name
        try:
            suggested_name = self.format_pattern % complete_data
            return self._sanitize_lot_name(suggested_name, product.id, ref_value)
        except Exception:
            # Ultimate fallback
            return partial_name

    def _sanitize_lot_name(self, lot_name, product_id, ref_value=None):
        """
        Sanitize lot name and return it if valid, empty string otherwise.

        Args:
            lot_name (str): Lot name to sanitize
            product_id (int): Product ID for validation

        Returns:
            str: Valid lot name or empty string
        """
        validation = self._verify_lot_name_format(
            lot_name, product_id=product_id, ref_value=ref_value
        )
        return lot_name if validation["valid"] else ""

    def _extract_partial_data(self, partial_name, required_placeholders):
        """
        Extract data from partial name considering pattern length and structure.

        Args:
            partial_name (str): Partial input name
            required_placeholders (list): Required placeholders from pattern

        Returns:
            dict: Extracted data based on partial match
        """
        extracted_data = {}

        # First try full regex match
        try:
            pattern_regex = self._create_regex_from_pattern()
            match = re.match(pattern_regex, partial_name)
            if match:
                return match.groupdict()
        except (re.error, ValueError, TypeError):
            pass

        # If full match fails, try partial matching based on pattern structure
        # Analyze the format pattern to understand expected structure
        pattern_segments = self._analyze_pattern_segments(required_placeholders)

        # Try to match partial_name against pattern segments
        current_pos = 0
        for segment in pattern_segments:
            if current_pos >= len(partial_name):
                break

            if segment["type"] == "date":
                segment_length = segment["length"]
                if current_pos + segment_length <= len(partial_name):
                    segment_value = partial_name[
                        current_pos : current_pos + segment_length
                    ]

                    # Validate date segment
                    if self._validate_date_segment(
                        segment["placeholder"], segment_value
                    ):
                        placeholder_name = (
                            segment["placeholder"].replace("%(", "").replace(")s", "")
                        )

                        # Normalize date values for 2-digit parameters
                        normalized_value = self._normalize_date_value(
                            segment_value, placeholder_name
                        )
                        extracted_data[placeholder_name] = normalized_value

                        # Add related date formats
                        if placeholder_name == "yy":
                            extracted_data["yyyy"] = f"20{normalized_value}"
                        elif placeholder_name == "yyyy":
                            extracted_data["yy"] = normalized_value[-2:]

                    current_pos += segment_length
                else:
                    # Partial segment - try to extract what we can
                    remaining = partial_name[current_pos:]
                    if remaining and self._validate_date_segment(
                        segment["placeholder"], remaining, partial=True
                    ):
                        placeholder_name = (
                            segment["placeholder"].replace("%(", "").replace(")s", "")
                        )

                        # Normalize partial date values for 2-digit parameters
                        normalized_value = self._normalize_date_value(
                            remaining, placeholder_name
                        )
                        extracted_data[placeholder_name] = normalized_value
                    break
            elif segment["type"] == "literal":
                # Skip literal characters if they match
                literal_length = len(segment["value"])
                if current_pos + literal_length <= len(partial_name):
                    if (
                        partial_name[current_pos : current_pos + literal_length]
                        == segment["value"]
                    ):
                        current_pos += literal_length
                    else:
                        break
                else:
                    break

        return extracted_data

    def _analyze_pattern_segments(self, required_placeholders):
        """
        Analyze format_pattern to understand its structure and segments.

        Returns:
            list: List of pattern segments with type and properties
        """
        segments = []
        pattern = self.format_pattern

        # Find all placeholders and their positions
        placeholder_matches = list(re.finditer(r"%\((\w+)\)s", pattern))

        current_pos = 0
        for match in placeholder_matches:
            # Add literal text before placeholder
            if match.start() > current_pos:
                literal_text = pattern[current_pos : match.start()]
                if literal_text:
                    segments.append({"type": "literal", "value": literal_text})

            # Add placeholder
            placeholder = match.group(0)
            placeholder_name = match.group(1)

            segment = {
                "type": (
                    "date"
                    if placeholder_name in ["yy", "yyyy", "mm", "dd"]
                    else "other"
                ),
                "placeholder": placeholder,
                "name": placeholder_name,
            }

            # Determine expected length
            if placeholder_name == "yy":
                segment["length"] = 2
            elif placeholder_name == "yyyy":
                segment["length"] = 4
            elif placeholder_name in ["mm", "dd"]:
                segment["length"] = 2
            else:
                segment["length"] = "variable"

            segments.append(segment)
            current_pos = match.end()

        # Add remaining literal text
        if current_pos < len(pattern):
            literal_text = pattern[current_pos:]
            if literal_text:
                segments.append({"type": "literal", "value": literal_text})

        return segments

    def _validate_date_segment(self, placeholder, value, partial=False):
        """
        Validate a date segment value.

        Args:
            placeholder (str): The placeholder name (e.g., '%(yy)s')
            value (str): The value to validate
            partial (bool): Whether this is a partial validation

        Returns:
            bool: True if valid
        """
        if not value.isdigit():
            return False

        placeholder_name = placeholder.replace("%(", "").replace(")s", "")

        try:
            int_value = int(value)

            if placeholder_name == "yy":
                return len(value) == 2 or (partial and len(value) < 2)
            elif placeholder_name == "yyyy":
                return len(value) == 4 or (partial and len(value) < 4)
            elif placeholder_name == "mm":
                if partial and len(value) == 1:
                    return 1 <= int_value <= 9
                return len(value) == 2 and 1 <= int_value <= 12
            elif placeholder_name == "dd":
                if partial and len(value) == 1:
                    return 1 <= int_value <= 9
                return len(value) == 2 and 1 <= int_value <= 31

        except ValueError:
            return False

        return True

    def _normalize_date_value(self, value, placeholder_name):
        """
        Normalize date value for 2-digit parameters, converting "0" or "" to "00".

        Args:
            value (str): The date value to normalize
            placeholder_name (str): The placeholder name (yy, mm, dd, etc.)

        Returns:
            str: Normalized date value
        """
        # Handle empty string or "0" for 2-digit date parameters
        if placeholder_name in ["yy", "mm", "dd"]:
            if value == "" or value == "0":
                return "00"
            elif len(value) == 1 and value.isdigit():
                return value.zfill(2)  # "1" -> "01"

        return value

    def _verify_lot_name_format(self, lot_name, product_id=None, ref_value=None):
        """
        Validate if a lot name complies with the rule's format pattern.

        Args:
            lot_name (str): The lot name to validate
            product_id (int, optional): Product ID for validation

        Returns:
            dict: {
                'valid': bool,
                'error': str or None,
                'message': str
            }
        """
        self.ensure_one()

        result = {"valid": False, "error": None, "message": ""}

        if not lot_name:
            result["error"] = "Lot name cannot be empty"
            result["message"] = "❌ Nombre del lote vacío"
            return result

        try:
            # Create regex pattern from format pattern
            pattern_regex = self._create_regex_from_pattern()

            # Match the lot name against the pattern
            match = re.match(pattern_regex, lot_name)
            if not match:
                result["error"] = (
                    f"Lot name '{lot_name}' doesn't match expected format: {self.format_pattern}"
                )
                result["message"] = (
                    f"❌ Formato incorrecto. Esperado: {self.format_pattern}"
                )
                return result

            # Extract components
            date_info = match.groupdict()

            # Validate date components
            year = None
            if "yyyy" in date_info:
                year = int(date_info["yyyy"])
            elif "yy" in date_info:
                yy = int(date_info["yy"])
                year = 2000 + yy if yy <= 30 else 1900 + yy

            if not year:
                result["error"] = "Could not extract valid year from lot name"
                result["message"] = "❌ Año inválido en el nombre del lote"
                return result

            month = 1
            if "mm" in date_info:
                month = int(date_info["mm"])
                if month < 1 or month > 12:
                    result["error"] = (
                        f"Invalid month '{month}'. Must be between 01 and 12"
                    )
                    result["message"] = f"❌ Mes inválido: {month}"
                    return result

            day = 1
            if "dd" in date_info:
                day = int(date_info["dd"])
                if day < 1 or day > 31:
                    result["error"] = f"Invalid day '{day}'. Must be between 01 and 31"
                    result["message"] = f"❌ Día inválido: {day}"
                    return result

            # Validate date exists
            try:
                from datetime import datetime

                test_date = datetime(year, month, day)
            except ValueError as e:
                result["error"] = f"Invalid date: {year}-{month:02d}-{day:02d}"
                result["message"] = f"❌ Fecha inválida: {year}-{month:02d}-{day:02d}"
                return result

            # Validate product_id if provided
            if product_id and "product_id" in date_info:
                extracted_product_id = date_info["product_id"]
                if str(product_id) != extracted_product_id:
                    result["error"] = (
                        f"Product ID mismatch. Expected: {product_id}, Found: {extracted_product_id}"
                    )
                    result["message"] = (
                        f"❌ ID de producto no coincide. Esperado: {product_id}, Encontrado: {extracted_product_id}"
                    )
                    return result

            # Validate reference if present (allow VENDOR_LOT_NUMBER placeholder)
            if "ref" in date_info:
                extracted_ref = date_info["ref"]
                ref_value = ref_value or extracted_ref
                if ref_value != extracted_ref:
                    result["error"] = (
                        f"Reference mismatch. Expected: {ref_value}, Found: {extracted_ref}"
                    )
                    result["message"] = (
                        f"❌ Referencia de producto no coincide. Esperado: {ref_value}, Encontrado: {extracted_ref}"
                    )
                    return result

                elif not ref_value:
                    result["error"] = "Reference field cannot be empty"
                    result["message"] = "❌ Campo de referencia vacío"
                    return result

                # Allow VENDOR_LOT_NUMBER as valid placeholder
                elif ref_value == "VENDOR_LOT_NUMBER":
                    result["valid"] = True
                    result["message"] = (
                        f"⚠️ Placeholder válido, requiere referencia: {lot_name}"
                    )
                    return result

            # If all validations pass
            result["valid"] = True
            result["message"] = f"✅ Formato válido: {lot_name}"

        except (ValueError, TypeError, re.error) as e:
            result["error"] = f"Validation error: {str(e)}"
            result["message"] = f"❌ Error de validación: {str(e)}"
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["message"] = f"❌ Error inesperado: {str(e)}"

        return result

    def _compute_product_count(self):
        """Compute the number of products using this lot rule."""
        for rule in self:
            rule.product_count = self.env["product.template"].search_count(
                [("lot_rule_id", "=", rule.id)]
            )

    def action_view_products(self):
        """Action to view products using this lot rule."""
        self.ensure_one()
        return {
            "name": f"Products using {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "view_mode": "list,form",
            "domain": [("lot_rule_id", "=", self.id)],
            "context": {"default_lot_rule_id": self.id},
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_if_no_associated_records(self):
        """Prevent deletion of rules with associated records."""
        for rule in self:
            # Check if rule has products associated
            product_count = self.env["product.template"].search_count(
                [("lot_rule_id", "=", rule.id)]
            )

            if product_count > 0:
                raise ValidationError(
                    _(
                        "Cannot delete lot rule '%s' because it is used by %d product(s). "
                        "Please remove the rule from all products first or set it as inactive."
                    )
                    % (rule.name, product_count)
                )

            # Check if rule has lots associated
            lot_count = self.env["stock.lot"].search_count(
                [("lot_rule_id", "=", rule.id)]
            )

            if lot_count > 0:
                raise ValidationError(
                    _(
                        "Cannot delete lot rule '%s' because it is used by %d lot(s). "
                        "Please remove the rule from all lots first or set it as inactive."
                    )
                    % (rule.name, lot_count)
                )
