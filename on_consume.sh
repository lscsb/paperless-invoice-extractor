#!/bin/bash
# Paperless post-consume hook: extrahiert Rechnungsdaten aus neu konsumierten Dokumenten.
#
# Einrichten in der Paperless-Konfiguration (paperless.conf oder docker-compose.env):
#   PAPERLESS_POST_CONSUME_SCRIPT=/opt/invoice-extract/on_consume.sh
#
# Paperless setzt u.a. folgende Umgebungsvariablen:
#   DOCUMENT_ID         – ID des neu konsumierten Dokuments
#   DOCUMENT_FILE_NAME  – Originaldateiname

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/invoice-extract.log"

# Paperless-Zugangsdaten – Token einmalig im Admin unter
# /admin/authtoken/tokenproxy/ anlegen oder per Django-Shell:
#   python manage.py drf_create_token <benutzername>
export PAPERLESS_URL="http://localhost:8000"
export PAPERLESS_TOKEN="<token-hier-eintragen>"

echo "$(date '+%Y-%m-%d %H:%M:%S') Dokument $DOCUMENT_ID ($DOCUMENT_FILE_NAME)" >> "$LOG_FILE"

"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/invoice_extract.py" \
    extract --document "$DOCUMENT_ID" \
    >> "$LOG_FILE" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') fertig (Exit $?)" >> "$LOG_FILE"
