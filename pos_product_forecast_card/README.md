# POS Product Forecast Card

This Odoo module adds a forecast card to each product in the Point of Sale (POS) interface, displaying the forecasted (virtual available) quantity for each product. It allows configuration of which warehouses to include in the forecast calculation, providing visual feedback and helping users make better sales decisions and avoid stockouts.

## Features

- Displays a forecast card with the predicted quantity on each POS product.
- Allows selection of warehouses to include in the forecast calculation from POS settings.
- Visual feedback with color coding (green, orange, red) based on stock levels.
- Prevents selling products with zero forecasted quantity (optional validation).
- Fully integrated with Odoo's OWL frontend framework for a reactive and modern UI.

## Configuration

1. Go to **Point of Sale > Configuration > Point of Sale** and select your POS.
2. Enable the option **Show Product Forecast**.
3. Select the warehouses to include in the forecast calculation. If none are selected, all warehouses will be considered.
4. Save the configuration.

## How it Works

- The backend exports the selected configuration to the POS frontend.
- The forecast card is shown only for storable products and when the option is enabled.
- The card updates automatically based on the selected warehouses and product.
- If the forecasted quantity is zero, the module can block the sale and show a warning.

## Visual Example

![Forecast Card Example](static/description/icon.png)

## Technical Highlights

- Backend: Extends `pos.config` and `res.config.settings` to manage warehouse selection and forecast settings.
- Frontend: Patches OWL's `ProductCard` and `ProductScreen` to display the card and validate sales.
- Styles: Custom CSS for a modern, responsive, and visually appealing card.

## Authors

- German, Jeziel

## License

LGPL-3
