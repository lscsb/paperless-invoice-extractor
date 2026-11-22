# CLAUDE.md — Entwicklungshinweise für invoice_extract

## Tests ausführen

```bash
python -m pytest -v                  # alle Tests
python -m pytest tests/test_pipeline.py -v   # nur Pipeline-Tests
```

Alle Tests sind selbstständig (keine laufende Paperless-Instanz nötig).
`tests/test_integration.py` erzeugt echte PDFs mit `fpdf2`/`segno` und braucht `libzbar0`.

---

## Paperless-ngx REST API — wichtige Versionsfakten

### Versionsaushandlung

Der Client sendet `Accept: application/json; version=N`.
Paperless-ngx 3.x unterstützt **nur API v9 und v10** — v1–v8 wurden gestrichen.
Bei einer nicht unterstützten Version antwortet der Server mit **HTTP 406** und dem Header
`X-Api-Version: <höchste-unterstützte-Version>` (z. B. `10`).
Der Client wirft dann `PaperlessVersionError` mit der Information aus dem Header.

### Select-Felder (Custom Fields mit `data_type: "select"`)

Ab API **v7** (Paperless-ngx 2.14+) gelten andere Formate als zuvor:

| Aspekt | API v5/v6 (alt) | API v7+ / v10 (aktuell) |
|---|---|---|
| `extra_data.select_options` in GET-Antwort | `["Option A", "Option B"]` | `[{"id": "16-Zeichen-String", "label": "Option A"}, …]` |
| Wert beim Schreiben (PATCH) | String-Label `"Option A"` | String-ID `"5t7Ix9oT5zdhPVrV"` |
| Wert beim Lesen (GET Dokument) | String-Label | String-ID |

Die IDs sind **16-stellige zufällige Strings**, die der Server beim Anlegen des Feldes generiert.
Sie sind stabil (solange das Feld nicht gelöscht und neu angelegt wird).

**Rückwärtskompatibilität im Code:** `_get_select_option_value()` und
`_get_select_option_label()` in `pipeline.py` erkennen das Format automatisch
(erstes Element ein dict → v10, ein String → ältere API) und verhalten sich entsprechend.

### Weitere Änderungen v5 → v10 (Überblick)

- **v2:** `Tag.colour` (Integer) → `Tag.color` (Hex-String `"#a6cee3"`) + `Tag.text_color`
- **v7:** select_options-Format wie oben
- **v9:** `Document.created` ist jetzt ein reiner Datumsstring (`2024-01-15`), kein Datetime mehr
- **v10:** `SavedView.show_on_dashboard/show_in_sidebar` entfernt; Bulk-Edit-Operationen
  (rotate, merge, split …) haben eigene Endpunkte; `/api/tasks/` ist jetzt paginiert

---

## Konfiguration: API-Version

Die API-Version lässt sich auf drei Wegen festlegen (höhere Prio schlägt niedrigere):

1. **Umgebungsvariable** `PAPERLESS_API_VERSION=10`
2. **config.yml** unter `paperless.api_version: 10`
3. **Standard** im Code: `Config.api_version = 10`

`load_config()` in `extract_config.py` liest beides — auch ohne YAML-Datei wird die
Umgebungsvariable ausgewertet.

---

## Architektur-Kurzüberblick

```
invoice_extract.py      CLI, lädt Config zuerst, erstellt dann Client mit cfg.api_version
    ↓
paperless_client.py     HTTP-Client; PaperlessVersionError bei 406
    ↓
pipeline.py             Orchestrierung; _field_cache für Select-Option-Lookup
    ↓
parsers/                erechnung.py (CII + UBL), girocode.py (EPC-QR)
    ↓
validators.py           IBAN (mod-97), Beträge, Datumsfelder
```

**Schreibschutz:** Felder werden nur geschrieben, wenn ihr aktueller Wert `None` oder `""`
ist — nicht einfach falsy (wichtig: Select-IDs können theoretisch mit `"0"` beginnen).
Ist `Rechnungs-Datenquelle` auf `manuell` gesetzt, wird das Dokument komplett übersprungen.
Der Check nutzt `_get_select_option_label()`, damit Integer-IDs korrekt aufgelöst werden.

---

## Test-Fixtures für API v10

In `tests/test_pipeline.py` repräsentieren die Konstanten `_DS_ID_ERECHNUNG`,
`_DS_ID_GIROCODE`, `_DS_ID_MANUELL` die 16-stelligen String-IDs der Select-Optionen.
`_default_fields()` gibt das v10-Format mit `{id, label}`-Dicts zurück.
Beim Testen der `manuell`-Schutzlogik muss der Dokument-Mock die String-ID verwenden,
nicht den Label-String.
