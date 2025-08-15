from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"


    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    @api.model
    def _get_lenght_uom_id_from_ir_config_parameter(self):
        """Get the unit of measure to interpret the `lenght` field. By default, we considerer
        that lenghts are expressed in meters. Users can configure to express them in yards
        by adding an ir.config_parameter record with "product.lenght_in_yd" as key
        and "1" as value."""
        product_lenght_in_yd_param = (
            self.env["ir.config_parameter"].sudo().get_param("product.lenght_in_yd")
        )
        if product_lenght_in_yd_param == "1":
            return self.env.ref("uom.product_uom_yard")

        else:
            return self.env.ref("uom.product_uom_meter")

    @api.model
    def _get_lenght_uom_name_from_ir_config_parameter(self):
        return self._get_lenght_uom_id_from_ir_config_parameter().display_name

    @api.model
    def _get_odometer_uom_id_from_ir_config_parameter(self):
        """Get the unit of measure to interpret the `odometer` field. By default, we considerer
        that odometers are expressed in kilometers. Users can configure to express them in miles
        by adding an ir.config_parameter record with "product.odometer_in_mi" as key
        and "1" as value."""
        product_odometer_in_mi_param = (
            self.env["ir.config_parameter"].sudo().get_param("product.odometer_in_mi")
        )
        if product_odometer_in_mi_param == "1":
            return self.env.ref("uom.product_uom_mile")

        else:
            return self.env.ref("uom.product_uom_km")

    @api.model
    def _get_odometer_uom_name_from_ir_config_parameter(self):
        return self._get_odometer_uom_id_from_ir_config_parameter().display_name

    @api.model
    def _get_area_uom_id_from_ir_config_parameter(self):
        """Get the unit of measure to interpret the `area` field. By default, we considerer
        that areas are expressed in square meters. Users can configure to express them in square feet
        by adding an ir.config_parameter record with "product.area_in_square_ft" as key
        and "1" as value."""
        product_area_in_square_feet_param = (
            self.env["ir.config_parameter"].sudo().get_param("product.area_in_square_ft")
        )
        if product_area_in_square_feet_param == "1":
            return self.env.ref("uom.product_uom_square_foot")

        else:
            return self.env.ref("uom.product_uom_square_meter")

    @api.model
    def _get_area_uom_name_from_ir_config_parameter(self):
        return self._get_area_uom_id_from_ir_config_parameter().display_name

    @api.model
    def _get_power_uom_id_from_ir_config_parameter(self):
        """Get the unit of measure to interpret the `power` field. By default, we considerer
        that power is expressed in kilowatts. Users can configure to express it in horsepower
        by adding an ir.config_parameter record with "product.power_in_hp" as key
        and "1" as value."""
        product_power_in_hp_param = (
            self.env["ir.config_parameter"].sudo().get_param("product.power_in_hp")
        )
        if product_power_in_hp_param == "1":
            return self.env.ref("uom_extended.product_uom_hp")

        else:
            return self.env.ref("uom_extended.product_uom_kw")

    @api.model
    def _get_power_uom_name_from_ir_config_parameter(self):
        return self._get_power_uom_id_from_ir_config_parameter().display_name

    @api.model
    def _get_fuel_efficiency_uom_id_from_ir_config_parameter(self):
        """Get the unit of measure to interpret the `fuel_efficiency` field. By default, we considerer
        that fuel efficiency is expressed in km/l. Users can configure to express it in mpg
        by adding an ir.config_parameter record with "product.fuel_efficiency_in_mpg" as key
        and "1" as value."""
        product_fuel_efficiency_in_mpg_param = (
            self.env["ir.config_parameter"].sudo().get_param("product.fuel_efficiency_in_mpg")
        )
        if product_fuel_efficiency_in_mpg_param == "1":
            return self.env.ref("uom_extended.product_uom_miles_per_galon")

        else:
            return self.env.ref("uom_extended.product_uom_km_per_liter")

    @api.model
    def _get_fuel_efficiency_uom_name_from_ir_config_parameter(self):
        return self._get_fuel_efficiency_uom_id_from_ir_config_parameter().display_name
