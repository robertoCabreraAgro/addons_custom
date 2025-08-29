import re

from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockLot(models.Model):
    _inherit = "stock.lot"

    lot_rule_id = fields.Many2one(
        comodel_name="stock.lot.rule",
        string="Lot Rule",
        index=True,
        help="Rule used for this lot nomenclature and date calculations",
    )
    # Override existing ref field to make it computed from lot name (readonly)
    ref = fields.Char(
        string="Reference",
        compute="_compute_ref",
        store=True,
        readonly=True,
        help="Vendor lot number extracted from lot name",
    )
    manufacture_date = fields.Date(
        string="Manufacturing Date",
        compute="_compute_manufacture_date",
        store=True,
        readonly=True,
        help="Manufacturing date extracted from lot name",
    )
    # Override existing fields to make them computed from manufacture_date
    expiration_date = fields.Datetime(
        string="Expiration Date",
        compute="_compute_lot_dates",
        store=True,
        readonly=False,
        help="Computed from manufacturing date using lot rule, or manually entered",
    )
    use_date = fields.Datetime(
        string="Best Before Date",
        compute="_compute_lot_dates",
        store=True,
        readonly=False,
        help="Computed from manufacturing date using lot rule, or manually entered",
    )
    removal_date = fields.Datetime(
        string="Removal Date",
        compute="_compute_lot_dates",
        store=True,
        readonly=False,
        help="Computed from manufacturing date using lot rule, or manually entered",
    )
    alert_date = fields.Datetime(
        string="Alert Date",
        compute="_compute_lot_dates",
        store=True,
        readonly=False,
        help="Computed from manufacturing date using lot rule, or manually entered",
    )

    @api.constrains("name", "product_id", "lot_rule_id")
    def _check_lot_rule_id(self):
        """Constraint to validate lot name compliance with lot rule"""
        for lot in self:
            # Get lot rule (cache once)
            lot_rule = lot.lot_rule_id or (
                lot.product_id and lot.product_id.lot_rule_id
            )
            if not lot_rule or not lot.name:
                continue

            # Compatibility check (fast validation first)
            if (
                lot.lot_rule_id
                and lot.product_id
                and lot.product_id.lot_rule_id
                and lot.lot_rule_id != lot.product_id.lot_rule_id
            ):
                raise ValidationError(
                    _("Lot rule '%s' is not compatible with product '%s' rule '%s'")
                    % (
                        lot.lot_rule_id.name,
                        lot.product_id.display_name,
                        lot.product_id.lot_rule_id.name,
                    )
                )

            # Format validation using optimized method
            result = lot_rule._verify_lot_name_format(lot.name, lot.product_id.id)
            if not result["valid"]:
                raise ValidationError(result["error"])

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to automatically compute dates from lot name"""
        # Optimize product calls for batch processing
        product_ids = [
            vals.get("product_id")
            for vals in vals_list
            if vals.get("product_id") and "lot_rule_id" not in vals
        ]

        if product_ids:
            # Get all products in one query
            products = self.env["product.product"].browse(product_ids)
            products_dict = {p.id: p for p in products}

            # Assign lot_rule_id to vals_list
            for vals in vals_list:
                if vals.get("product_id") and "lot_rule_id" not in vals:
                    product = products_dict.get(vals["product_id"])
                    if product and product.lot_rule_id:
                        vals["lot_rule_id"] = product.lot_rule_id.id

        return super().create(vals_list)

    @api.depends("name", "lot_rule_id", "product_id")
    def _compute_ref(self):
        """Compute reference from lot name using lot rule."""
        for lot in self:
            lot_rule = lot.lot_rule_id or (
                lot.product_id and lot.product_id.lot_rule_id
            )
            lot_ref = lot.ref

            if not lot_rule or not lot.name:
                lot.ref = lot_ref
                continue

            # Check if pattern uses %(ref)s
            uses_ref = "%(ref)s" in lot_rule.format_pattern
            if not uses_ref:
                lot.ref = lot_ref
                continue

            try:
                # Extract reference using the format pattern
                pattern_regex = lot_rule._create_regex_from_pattern()
                match = re.match(pattern_regex, lot.name)
                if match:
                    date_info = match.groupdict()
                    if "ref" in date_info:
                        ref_part = date_info["ref"]
                        # Don't set placeholder as actual ref value
                        if ref_part and ref_part != "VENDOR_LOT_NUMBER":
                            lot.ref = ref_part
                        else:
                            lot.ref = lot_ref
                    else:
                        lot.ref = lot_ref
                else:
                    lot.ref = lot_ref
            except (re.error, ValueError, TypeError):
                lot.ref = lot_ref

    @api.depends("name", "lot_rule_id", "product_id")
    def _compute_manufacture_date(self):
        """Compute manufacture date from lot name using lot rule."""
        for lot in self:
            lot_rule = lot.lot_rule_id or (
                lot.product_id and lot.product_id.lot_rule_id
            )

            if not lot_rule or not lot.name:
                lot.manufacture_date = False
                continue

            try:
                manufacture_date = lot_rule._get_manufacture_date(lot.name)
                lot.manufacture_date = (
                    manufacture_date.date() if manufacture_date else False
                )
            except Exception:
                lot.manufacture_date = False

    @api.depends("manufacture_date", "lot_rule_id", "product_id")
    def _compute_lot_dates(self):
        """Compute expiration, use, removal and alert dates from manufacturing date"""
        for lot in self:
            # Get lot rule (check lot first, then product)
            lot_rule = lot.lot_rule_id or (
                lot.product_id and lot.product_id.lot_rule_id
            )

            if not lot.manufacture_date or not lot_rule:
                # If no manufacture_date or lot_rule, keep manual values (don't reset)
                continue

            manufacture_datetime = datetime.combine(
                lot.manufacture_date, datetime.min.time()
            )

            # Compute dates using the lot rule
            expiration_date = lot_rule._get_expiration_date(manufacture_datetime)
            use_date = lot_rule._get_use_date(manufacture_datetime)
            removal_date = lot_rule._get_removal_date(manufacture_datetime)
            alert_date = lot_rule._get_alert_date(manufacture_datetime)

            # Update computed dates (keep as datetime to match original field type)
            lot.expiration_date = expiration_date if expiration_date else False
            lot.use_date = use_date if use_date else False
            lot.removal_date = removal_date if removal_date else False
            lot.alert_date = alert_date if alert_date else False

    @api.onchange("name")
    def _onchange_name_autocomplete(self):
        """Auto-complete lot name based on partial input"""
        if not self.name:
            return

        # Get lot rule (cache once)
        lot_rule = self.lot_rule_id or (self.product_id and self.product_id.lot_rule_id)
        if not lot_rule:
            return

        # Try to generate suggested name
        suggested_name = lot_rule._generate_lot_name(self.name, self.product_id)

        # Apply suggested name if different from current
        if suggested_name and suggested_name != self.name:
            # Update name (ref will be computed automatically)
            self.name = suggested_name

            # Prepare appropriate completion message
            warning = "VENDOR_LOT_NUMBER" in suggested_name
            message = self.env._("Lot name was auto-completed to: %s" % suggested_name)
            if warning:
                message = self.env._(
                    "Lot name pattern requires a vendor lot number. Please fill the 'Reference' field and complete the lot name manually."
                )

            self._send_simple_notification(message, warning=warning)

    def _send_simple_notification(self, message, warning=True):
        self.ensure_one()
        title = (
            self.env._("Lot Rule Warning") if warning else self.env._("Notification")
        )
        return self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "title": title,
                "sticky": warning,
                "warning": warning,
                "message": message,
            },
        )
