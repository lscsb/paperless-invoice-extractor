# invoice_extract

Kassierer-Tool: Liest Rechnungsdaten aus Paperless-ngx-Dokumenten aus.

Unterstützte Quellen:
- **E-Rechnung** (ZUGFeRD / Factur-X): eingebettete XML-Dateien im PDF (CII und UBL)
- **GiroCode** (EPC-QR): QR-Codes auf den ersten 3 Seiten des PDFs

Extrahierte Daten (Rechnungsnummer, Datum, Betrag, IBAN, BIC, Zahlungsreferenz) werden als
Custom Fields in Paperless gespeichert. Status-Tags (`Auslesen: E-Rechnung`, `Auslesen: GiroCode`
etc.) werden additiv hinzugefügt – bestehende Tags bleiben erhalten.

---

## Deployment auf dem Paperless-Server (Raspberry Pi)

### 1. Systempakete

```bash
sudo apt install libzbar0 python3-venv
```

`pypdfium2` bringt seinen eigenen PDFium-Build mit – `poppler-utils` wird **nicht** benötigt.

### 2. Skript kopieren

```bash
sudo cp -r tools/extract /opt/invoice-extract
sudo chown -R paperless:paperless /opt/invoice-extract
```

### 3. Python-Umgebung einrichten

```bash
cd /opt/invoice-extract
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 4. API-Token ermitteln

Im Paperless-Admin unter `/admin/authtoken/tokenproxy/` oder per Django-Shell:

```bash
cd /opt/paperless/src   # Paperless-Quellverzeichnis
python manage.py drf_create_token <benutzername>
```

### 5. Token in den Hook eintragen

In `on_consume.sh` die Zeile anpassen:

```bash
export PAPERLESS_TOKEN="<token-hier-eintragen>"
```

### 6. Ersteinrichtung: Custom Fields und Tags anlegen

```bash
cd /opt/invoice-extract
export PAPERLESS_URL=http://localhost:8000
export PAPERLESS_TOKEN=<token>

# Vorschau
venv/bin/python invoice_extract.py setup --dry-run

# Anlegen
venv/bin/python invoice_extract.py setup
```

### 7. Post-consume-Hook einrichten

In der Paperless-Konfiguration (`/etc/paperless.conf` oder `.env` bei Docker):

```
PAPERLESS_POST_CONSUME_SCRIPT=/opt/invoice-extract/on_consume.sh
```

Paperless neu starten, damit die Einstellung wirksam wird.

### 8. Testen

Ein Dokument manuell neu konsumieren lassen oder direkt aufrufen:

```bash
DOCUMENT_ID=42 DOCUMENT_FILE_NAME=test.pdf /opt/invoice-extract/on_consume.sh
```

Log einsehen:

```bash
tail -f /var/log/invoice-extract.log
```

---

## Manueller Aufruf

```bash
cd /opt/invoice-extract
export PAPERLESS_URL=http://localhost:8000
export PAPERLESS_TOKEN=<token>

# Alle unverarbeiteten Dokumente (Tag "unbearbeitet")
venv/bin/python invoice_extract.py extract

# Vorschau ohne Schreiben
venv/bin/python invoice_extract.py extract --dry-run

# Bestimmte Dokumente (auch bereits verarbeitete)
venv/bin/python invoice_extract.py extract --document 42 43 --force

# Bereits verarbeitete erneut verarbeiten
venv/bin/python invoice_extract.py extract --force
```

### Ausgabe

Pro Dokument eine Zeile:

```
[42] Rechnung Muster GmbH | E-Rechnung | Rechnungsnummer, Rechnungssumme, IBAN | Auslesen: E-Rechnung | —
```

Format: `[ID] Titel | Quelle | geschriebene Felder | hinzugefügte Tags | Warnungen`

Abschlusssummary: `N/M Dokumente verarbeitet.`

Exit-Code: 0 bei Erfolg, 1 bei Verbindungs-/API-Fehlern (nicht wenn „nichts gefunden").

---

## Konfiguration (optional)

Alle Paperless-Bezeichnungen (Feldnamen, Tag-Namen) sind konfigurierbar.
Vorlage: `config.sample.yml` → kopieren nach `config.yml` und anpassen.

```bash
venv/bin/python invoice_extract.py extract --config config.yml
```

---

## Schreibschutz

- Felder werden nur geschrieben, wenn sie **leer** sind.
- Ist das Feld `Rechnungs-Datenquelle` auf `manuell` gesetzt, wird das Dokument
  **komplett übersprungen** – von Hand gepflegte Werte bleiben unangetastet.

---

## Tests (Entwicklung)

```bash
cd /srv/http/sts
pip install -r tools/extract/requirements-dev.txt
python -m pytest tools/extract/tests/ -v
```

---

## Dateistruktur

```
tools/extract/
├── invoice_extract.py      # CLI entry point
├── paperless_client.py     # Paperless REST API client
├── pipeline.py             # Orchestration
├── setup_paperless.py      # Setup-Befehl
├── extract_config.py       # Konfiguration und Defaults
├── pdf_utils.py            # PDF: eingebettete Dateien + Seiten-Rendering
├── validators.py           # IBAN (mod-97), Beträge, Datumsfelder
├── on_consume.sh           # Paperless post-consume Hook
├── config.sample.yml       # Konfigurationsvorlage
├── parsers/
│   ├── erechnung.py        # ZUGFeRD/Factur-X (CII und UBL)
│   └── girocode.py         # GiroCode/EPC-QR-Parser
├── requirements.txt
├── requirements-dev.txt
└── tests/
    ├── conftest.py
    ├── test_validators.py
    ├── test_girocode.py
    ├── test_erechnung.py
    ├── test_pipeline.py
    ├── test_integration.py
    └── fixtures/
        ├── cii_minimal.xml
        └── ubl_minimal.xml
```
