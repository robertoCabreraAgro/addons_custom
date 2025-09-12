#!/bin/bash
# Script: Anonymize the mounted DB, neutralize again if needed, and compress into tar.gz
# Run as: bash anonymize_compress.sh

DB_NAME="marin182"
DB_USER="roberto-cabrera"
ODOO_BIN_PATH="$HOME/instancias/odoo/odoo-bin"
ODOO_CONF_PATH="$HOME/instancias/conf/agromarin.conf"
FILESTORE_PATH="$HOME/.local/share/Odoo/filestore/$DB_NAME"
BACKUP_DIR="$HOME/instancias/db"
SANITIZED_BACKUP_FILE="$BACKUP_DIR/odoo_sanitized_backup.tar.gz"
TEMP_DIR="$BACKUP_DIR/temp_sanitized"
DUMP_FILE="$TEMP_DIR/dump.sql"

echo "=== Starting anonymization, neutralization, and compression for $DB_NAME ==="

# 1. Anonymize with SQL
echo "[1/6] Anonymizing DB..."
if ! psql -U "$DB_USER" -d "$DB_NAME" <<EOF
UPDATE res_partner SET
    name = 'Contacto Anonym ' || id,
    email = 'fake' || id || '@example.com',
    phone = '555-FAKE-' || id,
    mobile = '555-FAKE-' || id,
    street = 'Calle Fake ' || id,
    street2 = 'Colonia Fake',
    city = 'Ciudad Fake',
    zip = '00000',
    vat = 'RFC-FAKE-' || id;

UPDATE hr_employee SET
    work_email = 'emp' || id || '@fake.com',
    work_phone = '555-EMP-' || id,
    mobile_phone = '555-MOB-' || id,
    private_email = 'priv' || id || '@fake.com',
    private_street = 'Calle Emp Fake ' || id,
    private_street2 = 'Colonia Fake',
    private_city = 'Ciudad Fake',
    private_zip = '00000',
    ssnid = 'SSN-FAKE-' || id,
    l10n_mx_rfc = 'RFC-EMP-FAKE-' || id,
    l10n_mx_curp = 'CURP-FAKE-' || id;

UPDATE hr_payslip SET
    net_wage = 10000;
UPDATE res_users SET
    login = 'sistemas',
    password = 'sistemas'
WHERE id = 1059;
EOF
then
    echo "❌ Error during anonymization"
    exit 1
fi

# 2. Neutralize DB
echo "[2/6] Neutralizing DB..."
if ! "$ODOO_BIN_PATH" neutralize --db-filter=$DB_NAME -d $DB_NAME -c "$ODOO_CONF_PATH"; then
    echo "❌ Error during neutralization"
    exit 1
fi

# 3. Create temp dir for backup
echo "[3/6] Creating temporary backup dir..."
if ! mkdir -p "$TEMP_DIR"; then
    echo "❌ Error creating temp dir"
    exit 1
fi

# 4. Dump the anonymized DB
echo "[4/6] Dumping DB..."
if ! pg_dump -U "$DB_USER" "$DB_NAME" > "$DUMP_FILE"; then
    echo "❌ Error dumping DB"
    exit 1
fi

# 5. Copy filestore
echo "[5/6] Copying filestore..."
if ! mkdir -p "$TEMP_DIR/filestore" || ! cp -r "$FILESTORE_PATH/." "$TEMP_DIR/filestore"; then
    echo "⚠️ Warning: Filestore copy failed"
fi

# 6. Compress
echo "[6/6] Compressing backup..."
cd "$TEMP_DIR" || exit 1
if ! tar -czf "$SANITIZED_BACKUP_FILE" .; then
    echo "❌ Error compressing backup"
    exit 1
fi

# Cleanup
rm -rf "$TEMP_DIR"

echo "✅ Anonymized and neutralized backup created at $SANITIZED_BACKUP_FILE"
