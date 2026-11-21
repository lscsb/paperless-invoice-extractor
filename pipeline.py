"""Orchestration pipeline: select documents, extract, validate, write."""

from __future__ import annotations

import sys
from typing import Optional

from paperless_client import PaperlessClient, PaperlessError
from pdf_utils import extract_embedded_xmls, render_pages_as_images
from parsers.erechnung import parse_xml, InvoiceData
from parsers.girocode import parse_girocode, GiroCodeData
from validators import validate_iban, normalize_iban, validate_amount
from extract_config import Config


# ---------------------------------------------------------------------------
# ID caches (populated at runtime)
# ---------------------------------------------------------------------------

_field_id_cache: dict[str, int] = {}
_tag_id_cache:   dict[str, int] = {}


def _load_caches(client: PaperlessClient) -> None:
    global _field_id_cache, _tag_id_cache
    _field_id_cache = {f['name']: f['id'] for f in client.get_custom_fields()}
    _tag_id_cache   = {t['name']: t['id'] for t in client.get_tags()}


def _field_id(name: str) -> Optional[int]:
    return _field_id_cache.get(name)


def _tag_id(name: str) -> Optional[int]:
    return _tag_id_cache.get(name)


def _ensure_tag(client: PaperlessClient, name: str) -> Optional[int]:
    tid = _tag_id(name)
    if tid is None:
        t = client.create_tag(name)
        _tag_id_cache[name] = t['id']
        tid = t['id']
    return tid


# ---------------------------------------------------------------------------
# Monetary formatting
# ---------------------------------------------------------------------------

def _format_monetary(amount_str: Optional[str]) -> Optional[str]:
    if amount_str is None:
        return None
    try:
        return f'{float(amount_str):.2f}'
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Document selection
# ---------------------------------------------------------------------------

def _has_auslesen_tag(doc: dict, tag_names: dict[int, str], cfg: Config) -> bool:
    auslesen_names = {cfg.tag_erechnung, cfg.tag_girocode, cfg.tag_not_found, cfg.tag_conflict}
    for tid in doc.get('tags', []):
        if tag_names.get(tid, '') in auslesen_names:
            return True
    return False


def select_documents(client: PaperlessClient,
                     cfg: Config,
                     document_ids: list[int],
                     force: bool) -> list[dict]:
    tag_names = {v: k for k, v in _tag_id_cache.items()}

    if document_ids:
        docs = [client.get_document(did) for did in document_ids]
    else:
        inbox_id = _tag_id(cfg.tag_inbox)
        if inbox_id is None:
            print(f'WARNUNG: Tag "{cfg.tag_inbox}" nicht gefunden – alle Dokumente werden verarbeitet',
                  file=sys.stderr)
            docs = client.get_documents()
        else:
            docs = client.get_documents(tag_ids=[inbox_id])

    if not force:
        docs = [d for d in docs if not _has_auslesen_tag(d, tag_names, cfg)]

    return docs


# ---------------------------------------------------------------------------
# Field read helpers
# ---------------------------------------------------------------------------

def _get_field_value(doc: dict, field_name: str) -> Optional[str]:
    fid = _field_id(field_name)
    if fid is None:
        return None
    for cf in doc.get('custom_fields', []):
        if cf.get('field') == fid:
            return cf.get('value')
    return None


# ---------------------------------------------------------------------------
# GiroCode scanning (shared between main path and contradiction check)
# ---------------------------------------------------------------------------

def _scan_girocodes(pdf_bytes: bytes) -> list[GiroCodeData]:
    try:
        images = render_pages_as_images(pdf_bytes)
    except Exception:
        return []
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode, ZBarSymbol
    except ImportError:
        return []
    candidates: list[GiroCodeData] = []
    for img in images:
        for item in pyzbar_decode(img, symbols=[ZBarSymbol.QRCODE]):
            text = item.data.decode('utf-8', errors='replace')
            gc = parse_girocode(text)
            if gc is not None:
                candidates.append(gc)
    return candidates


def _pick_girocode(candidates: list[GiroCodeData]) -> tuple[Optional[GiroCodeData], bool]:
    """Return (girocode_or_None, has_contradiction)."""
    if not candidates:
        return None, False
    first = candidates[0]
    contradiction = any(
        gc.iban != first.iban or gc.amount != first.amount
        for gc in candidates[1:]
    )
    return (None if contradiction else first), contradiction


# ---------------------------------------------------------------------------
# Per-document processing
# ---------------------------------------------------------------------------

def process_document(client: PaperlessClient,
                     cfg: Config,
                     doc: dict,
                     dry_run: bool = False) -> str:
    doc_id = doc['id']
    title  = doc.get('title', '')
    warnings: list[str] = []
    new_tags:   list[int] = []
    new_fields: list[dict] = []
    fields_written: list[str] = []

    # Download PDF
    pdf_bytes = client.download_document(doc_id)
    if not pdf_bytes.startswith(b'%PDF'):
        tag_id = _ensure_tag(client, cfg.tag_not_found)
        if not dry_run:
            client.patch_document(doc_id, tags=[tag_id])
        return f'[{doc_id}] {title} | — | — | {cfg.tag_not_found} | nicht PDF'

    current_doc = client.get_document(doc_id)

    # Write-protection: Datenquelle == 'manuell' → skip everything
    if _get_field_value(current_doc, cfg.field_data_source) == 'manuell':
        return f'[{doc_id}] {title} | manuell geschützt | — | — | WARNUNG: übersprungen'

    # --- Extraction ---
    invoice: Optional[InvoiceData] = None
    girocode: Optional[GiroCodeData] = None
    giro_contradiction = False

    xmls = extract_embedded_xmls(pdf_bytes)
    for _filename, xml_bytes in xmls:
        result = parse_xml(xml_bytes)
        if result is not None:
            invoice = result
            break

    if invoice is None:
        giro_candidates = _scan_girocodes(pdf_bytes)
        girocode, giro_contradiction = _pick_girocode(giro_candidates)

    # --- Nothing found / contradiction ---
    if invoice is None and girocode is None:
        if giro_contradiction:
            tag_id = _ensure_tag(client, cfg.tag_conflict)
            new_tags.append(tag_id)
            if not dry_run:
                client.patch_document(doc_id, tags=new_tags)
            return (f'[{doc_id}] {title} | GiroCode | — | '
                    f'{cfg.tag_conflict} | widersprüchliche QR-Codes')
        tag_id = _ensure_tag(client, cfg.tag_not_found)
        if not dry_run:
            client.patch_document(doc_id, tags=[tag_id])
        return f'[{doc_id}] {title} | — | — | {cfg.tag_not_found} | —'

    # --- Build field map ---
    if invoice is not None:
        source_label = 'E-Rechnung'
        new_tags.append(_ensure_tag(client, cfg.tag_erechnung))
        if invoice.is_credit_note:
            new_tags.append(_ensure_tag(client, cfg.tag_credit_note))

        raw_iban = invoice.iban
        if raw_iban and not validate_iban(raw_iban):
            warnings.append(f'IBAN ungültig: {raw_iban}')
            raw_iban = None
            new_tags.append(_ensure_tag(client, cfg.tag_conflict))

        field_map = {
            cfg.field_invoice_number:   invoice.invoice_number,
            cfg.field_invoice_date:     invoice.invoice_date,
            cfg.field_due_date:         invoice.due_date,
            cfg.field_amount:           _format_monetary(invoice.amount),
            cfg.field_payee:            invoice.seller_name,
            cfg.field_iban:             normalize_iban(raw_iban) if raw_iban else None,
            cfg.field_bic:              invoice.bic,
            cfg.field_payment_reference: invoice.payment_reference,
            cfg.field_data_source:      'E-Rechnung',
        }

    else:
        source_label = 'GiroCode'
        new_tags.append(_ensure_tag(client, cfg.tag_girocode))

        raw_amount = None
        if girocode.amount:
            raw = girocode.amount[3:] if girocode.amount.upper().startswith('EUR') else girocode.amount
            valid, _ = validate_amount(raw)
            if valid:
                raw_amount = raw
            else:
                warnings.append(f'Betrag ungültig: {girocode.amount}')

        raw_iban = girocode.iban
        if raw_iban and not validate_iban(raw_iban):
            warnings.append(f'IBAN ungültig: {raw_iban}')
            raw_iban = None
            new_tags.append(_ensure_tag(client, cfg.tag_conflict))

        field_map = {
            cfg.field_amount:            raw_amount,
            cfg.field_payee:             girocode.recipient,
            cfg.field_iban:              normalize_iban(raw_iban) if raw_iban else None,
            cfg.field_bic:               girocode.bic,
            cfg.field_payment_reference: girocode.reference,
            cfg.field_data_source:       'GiroCode',
        }

    # --- Write fields (only if currently empty) ---
    for field_name, value in field_map.items():
        if value is None:
            continue
        fid = _field_id(field_name)
        if fid is None:
            warnings.append(f'Feld "{field_name}" nicht in Paperless gefunden')
            continue
        if _get_field_value(current_doc, field_name):
            continue
        new_fields.append({'field': fid, 'value': value})
        fields_written.append(field_name)

    if not dry_run:
        client.patch_document(doc_id, tags=new_tags, custom_fields=new_fields)

    tag_names_added = [name for name, tid in _tag_id_cache.items() if tid in new_tags]
    warn_str = '; '.join(warnings) if warnings else '—'
    return (
        f'[{doc_id}] {title} | {source_label} | '
        f'{", ".join(fields_written) or "—"} | '
        f'{", ".join(tag_names_added) or "—"} | '
        f'{warn_str}'
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_extract(client: PaperlessClient,
                cfg: Config,
                document_ids: list[int] | None = None,
                dry_run: bool = False,
                force: bool = False) -> int:
    _load_caches(client)

    try:
        docs = select_documents(client, cfg, document_ids or [], force)
    except PaperlessError as e:
        print(f'ERROR: Paperless API-Fehler: {e}', file=sys.stderr)
        return 1

    if not docs:
        print('Keine Dokumente zu verarbeiten.')
        return 0

    success = 0
    for doc in docs:
        try:
            print(process_document(client, cfg, doc, dry_run=dry_run))
            success += 1
        except PaperlessError as e:
            print(f'[{doc["id"]}] ERROR: {e}', file=sys.stderr)
        except Exception as e:
            print(f'[{doc["id"]}] ERROR: {e}', file=sys.stderr)

    suffix = ' (dry-run)' if dry_run else ''
    print(f'\n{success}/{len(docs)} Dokumente verarbeitet{suffix}.')
    return 0
