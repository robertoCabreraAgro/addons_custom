# MS Quick Record Search

This Odoo module adds a powerful quick record search feature to the command palette, allowing users to search for records from any model directly from the Odoo backend UI.

## Usage

1. Open the command palette (usually with `Ctrl+K` or `Cmd+K`).
2. Type the model name and search term, e.g.:
   - `res.partner John`
   - `sale.order S00001`
   - `product.product Chair`
3. Matching records will be listed. Click a record to open it.

## Security

- The module respects Odoo's access rights. Users will only see models and records they are allowed to read.
