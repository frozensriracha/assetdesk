#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
DB="asset_accountability.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "Error: sqlite3 not installed on PATH." >&2
    exit 1
fi
for file in schema.sql insert_data.sql queries.sql transaction.sql; do
    if [[ ! -f "$file" ]]; then
        echo "Error: required file is missing: $file" >&2
        exit 1
    fi
done

# STRICT tables need sqlite3 to run properly
version=$(sqlite3 :memory: 'SELECT sqlite_version();')
IFS=. read -r major minor patch <<< "$version"
if (( major < 3 || (major == 3 && minor < 37) )); then
    echo "Error: SQLite 3.37+ is required; found $version." >&2
    exit 1
fi

echo "Recreating $DB..."
rm -f -- "$DB"
# must enable foreign keys each time
sqlite3 -bail -cmd 'PRAGMA foreign_keys = ON;' "$DB" < schema.sql
sqlite3 -bail -cmd 'PRAGMA foreign_keys = ON;' "$DB" < insert_data.sql

echo
echo "Checking database and foreign keys..."
integrity=$(sqlite3 -bail "$DB" 'PRAGMA integrity_check;')
fk_errors=$(sqlite3 -bail -cmd 'PRAGMA foreign_keys = ON;' "$DB" 'PRAGMA foreign_key_check;')
if [[ "$integrity" != "ok" || -n "$fk_errors" ]]; then
    printf 'Validation failed: %s\n%s\n' "$integrity" "$fk_errors" >&2
    exit 1
fi

echo
echo "Running queries..."
sqlite3 -bail -echo -header -column -cmd 'PRAGMA foreign_keys = ON;' "$DB" < queries.sql

echo
echo "Running transaction..."
if sqlite3 -bail -header -column -cmd 'PRAGMA foreign_keys = ON;' "$DB" < transaction.sql; then
    echo "Transaction demonstration completed; checkout changes were rolled back."
else
    echo "Transaction failed. Uncommitted changes were rolled back when the connection closed." >&2
    exit 1
fi

echo
echo "Done."
