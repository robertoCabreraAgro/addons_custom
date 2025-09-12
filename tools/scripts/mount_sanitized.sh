#!/bin/bash
# Script: Mount the full backup into marin182_sanitized DB and neutralize it
# Run as: bash mount_db.sh

DB_NAME="marin182_sanitized"
DUMP_FILE="$HOME/instancias/db/odoo_sanitized_backup/dump.sql"
ODOO_BIN_PATH="$HOME/instancias/odoo/odoo-bin"
ODOO_CONF_PATH="$HOME/instancias/conf/agromarin_sanitized.conf"

echo "=== Starting mount and neutralization for $DB_NAME ==="

# Drop DB if exists
echo "[1/5] Dropping DB if exists..."
if ! psql -c "DROP DATABASE IF EXISTS $DB_NAME;"; then
    echo "❌ Error dropping DB"
    exit 1
fi

# Create DB with template
echo "[2/5] Creating DB from template..."
if ! psql -c "CREATE DATABASE $DB_NAME ENCODING 'unicode' LC_COLLATE 'C' TEMPLATE=marintemplate;"; then
    echo "❌ Error creating DB"
    exit 1
fi

# Import dump
echo "[3/5] Importing dump..."
if ! psql -d "$DB_NAME" < "$DUMP_FILE"; then
    echo "❌ Error importing dump"
    exit 1
fi

# Neutralize DB
echo "[4/5] Neutralizing DB..."
if ! "$ODOO_BIN_PATH" neutralize --db-filter=$DB_NAME -d $DB_NAME -c "$ODOO_CONF_PATH"; then
    echo "❌ Error neutralizing DB"
    exit 1
fi

echo "✅ DB $DB_NAME mounted and neutralized successfully."

# Run Odoo with DB
echo "[5/5] Starting Odoo..."
"$ODOO_BIN_PATH" --db-filter=$DB_NAME -d $DB_NAME -c "$ODOO_CONF_PATH"
