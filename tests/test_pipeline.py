"""Tests for pipeline.py using responses to mock Paperless HTTP."""

import io
import json
import os
import sys

import pytest
import responses as responses_lib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from paperless_client import PaperlessClient
from extract_config import Config
import pipeline

PAPERLESS_URL = 'http://paperless.test'
TOKEN = 'testtoken'
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), 'rb') as f:
        return f.read()


def make_client():
    return PaperlessClient(base_url=PAPERLESS_URL, token=TOKEN)


def make_cfg(**overrides) -> Config:
    """Return a Config with default names (matching what test mocks register)."""
    return Config(**overrides)


def _minimal_pdf_with_xml(xml_bytes: bytes) -> bytes:
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_attachment('factur-x.xml', xml_bytes)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _minimal_plain_pdf() -> bytes:
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_doc(doc_id=1, title='Test Rechnung', tags=None, custom_fields=None):
    return {
        'id': doc_id,
        'title': title,
        'tags': tags or [],
        'custom_fields': custom_fields or [],
    }


def _default_fields():
    """Field list matching Config defaults."""
    return [
        {'id': 1,  'name': 'Rechnungsnummer',  'data_type': 'string',   'extra_data': {}},
        {'id': 2,  'name': 'Rechnungsdatum',   'data_type': 'date',     'extra_data': {}},
        {'id': 3,  'name': 'Fällig am',         'data_type': 'date',     'extra_data': {}},
        {'id': 4,  'name': 'Rechnungssumme',   'data_type': 'monetary', 'extra_data': {}},
        {'id': 5,  'name': 'Zahlungsempfänger',  'data_type': 'string',   'extra_data': {}},
        {'id': 6,  'name': 'IBAN',              'data_type': 'string',   'extra_data': {}},
        {'id': 7,  'name': 'BIC',               'data_type': 'string',   'extra_data': {}},
        {'id': 8,  'name': 'Zahlungsreferenz',  'data_type': 'string',   'extra_data': {}},
        {'id': 9,  'name': 'Rechnungs-Datenquelle', 'data_type': 'select',
         'extra_data': {'select_options': ['E-Rechnung', 'GiroCode', 'manuell']}},
    ]


def _default_tags():
    return [
        {'id': 10, 'name': 'unbearbeitet'},
        {'id': 11, 'name': 'Auslesen: E-Rechnung'},
        {'id': 12, 'name': 'Auslesen: Widerspruch'},
        {'id': 13, 'name': 'Auslesen: GiroCode'},
        {'id': 20, 'name': 'Auslesen: nichts gefunden'},
        {'id': 21, 'name': 'Gutschrift'},
    ]


def _register_standard_mocks(rsps, doc, pdf_bytes, fields=None, tags=None):
    base = PAPERLESS_URL
    rsps.add(responses_lib.GET, f'{base}/api/custom_fields/?page_size=1000',
             json={'results': fields or [], 'next': None})
    rsps.add(responses_lib.GET, f'{base}/api/tags/?page_size=1000',
             json={'results': tags or [], 'next': None})
    rsps.add(responses_lib.GET, f'{base}/api/documents/',
             json={'results': [doc], 'next': None})
    rsps.add(responses_lib.GET, f'{base}/api/documents/{doc["id"]}/', json=doc)
    rsps.add(responses_lib.GET,
             f'{base}/api/documents/{doc["id"]}/download/?original=true',
             body=pdf_bytes, content_type='application/pdf')
    rsps.add(responses_lib.PATCH, f'{base}/api/documents/{doc["id"]}/', json=doc)


@responses_lib.activate
def test_process_erechnung_doc():
    """E-Rechnung XML embedded → fields written, Auslesen: E-Rechnung tag added."""
    xml = load_fixture('cii_minimal.xml')
    pdf = _minimal_pdf_with_xml(xml)
    doc = _make_doc()

    _register_standard_mocks(responses_lib, doc, pdf,
                              fields=_default_fields(), tags=_default_tags())

    result = pipeline.run_extract(make_client(), make_cfg(), dry_run=False)
    assert result == 0

    patch_calls = [c for c in responses_lib.calls if c.request.method == 'PATCH']
    assert len(patch_calls) == 1
    body = json.loads(patch_calls[0].request.body)
    assert 11 in body['tags']                              # Auslesen: E-Rechnung
    field_ids = [cf['field'] for cf in body['custom_fields']]
    assert 1 in field_ids                                  # Rechnungsnummer


@responses_lib.activate
def test_nothing_found():
    """Plain PDF → Auslesen: nichts gefunden tag added."""
    pdf = _minimal_plain_pdf()
    doc = _make_doc()

    _register_standard_mocks(responses_lib, doc, pdf,
                              fields=_default_fields(), tags=_default_tags())

    result = pipeline.run_extract(make_client(), make_cfg(), dry_run=False)
    assert result == 0

    patch_calls = [c for c in responses_lib.calls if c.request.method == 'PATCH']
    assert len(patch_calls) == 1
    body = json.loads(patch_calls[0].request.body)
    assert 20 in body['tags']


@responses_lib.activate
def test_dry_run_no_writes():
    """dry_run=True → no PATCH calls made."""
    xml = load_fixture('cii_minimal.xml')
    pdf = _minimal_pdf_with_xml(xml)
    doc = _make_doc()

    _register_standard_mocks(responses_lib, doc, pdf,
                              fields=_default_fields(), tags=_default_tags())

    result = pipeline.run_extract(make_client(), make_cfg(), dry_run=True)
    assert result == 0

    patch_calls = [c for c in responses_lib.calls if c.request.method == 'PATCH']
    assert len(patch_calls) == 0


@responses_lib.activate
def test_manuell_protected():
    """Datenquelle=manuell → no writes."""
    xml = load_fixture('cii_minimal.xml')
    pdf = _minimal_pdf_with_xml(xml)

    doc = _make_doc(custom_fields=[{'field': 9, 'value': 'manuell'}])

    _register_standard_mocks(responses_lib, doc, pdf,
                              fields=_default_fields(), tags=_default_tags())

    result = pipeline.run_extract(make_client(), make_cfg(), dry_run=False)
    assert result == 0

    patch_calls = [c for c in responses_lib.calls if c.request.method == 'PATCH']
    assert len(patch_calls) == 0


@responses_lib.activate
def test_force_flag():
    """Doc with Auslesen: E-Rechnung tag → skipped without --force."""
    doc = _make_doc(tags=[11])  # already has Auslesen: E-Rechnung

    base = PAPERLESS_URL
    responses_lib.add(responses_lib.GET, f'{base}/api/custom_fields/?page_size=1000',
                      json={'results': _default_fields(), 'next': None})
    responses_lib.add(responses_lib.GET, f'{base}/api/tags/?page_size=1000',
                      json={'results': _default_tags(), 'next': None})
    responses_lib.add(responses_lib.GET, f'{base}/api/documents/',
                      json={'results': [doc], 'next': None})

    result = pipeline.run_extract(make_client(), make_cfg(), force=False)
    assert result == 0
    patch_calls = [c for c in responses_lib.calls if c.request.method == 'PATCH']
    assert len(patch_calls) == 0


@responses_lib.activate
def test_invalid_iban_adds_widerspruch():
    """Invalid IBAN in E-Rechnung → Auslesen: Widerspruch, IBAN not written."""
    xml = load_fixture('cii_minimal.xml')
    xml = xml.replace(b'DE71110220330123456789', b'DE00000000000000000000')
    pdf = _minimal_pdf_with_xml(xml)
    doc = _make_doc()

    _register_standard_mocks(responses_lib, doc, pdf,
                              fields=_default_fields(), tags=_default_tags())

    result = pipeline.run_extract(make_client(), make_cfg(), dry_run=False)
    assert result == 0

    patch_calls = [c for c in responses_lib.calls if c.request.method == 'PATCH']
    assert len(patch_calls) == 1
    body = json.loads(patch_calls[0].request.body)
    assert 12 in body['tags']                                     # Widerspruch
    field_ids_written = [cf['field'] for cf in body['custom_fields']]
    assert 6 not in field_ids_written                             # IBAN not written


@responses_lib.activate
def test_existing_tags_preserved():
    """Existing tags on a doc are preserved after patch."""
    xml = load_fixture('cii_minimal.xml')
    pdf = _minimal_pdf_with_xml(xml)

    existing_tag_id = 99
    doc = _make_doc(tags=[existing_tag_id])

    tags = _default_tags() + [{'id': existing_tag_id, 'name': 'ExistingTag'}]
    _register_standard_mocks(responses_lib, doc, pdf,
                              fields=_default_fields(), tags=tags)

    result = pipeline.run_extract(make_client(), make_cfg(), dry_run=False)
    assert result == 0

    patch_calls = [c for c in responses_lib.calls if c.request.method == 'PATCH']
    assert len(patch_calls) == 1
    body = json.loads(patch_calls[0].request.body)
    assert existing_tag_id in body['tags']   # preserved
    assert 11 in body['tags']               # new: Auslesen: E-Rechnung


@responses_lib.activate
def test_custom_config_names():
    """Config with non-default names is used for field lookup and tag selection."""
    xml = load_fixture('cii_minimal.xml')
    pdf = _minimal_pdf_with_xml(xml)
    doc = _make_doc()

    # Custom names differ from defaults
    cfg = Config(
        tag_inbox='Eingang',
        field_invoice_number='Nummer',
        field_amount='Betrag',
        field_payment_reference='Verwendungszweck',
    )

    custom_fields = [
        {'id': 1,  'name': 'Nummer',           'data_type': 'string',   'extra_data': {}},
        {'id': 4,  'name': 'Betrag',           'data_type': 'monetary', 'extra_data': {}},
        {'id': 8,  'name': 'Verwendungszweck', 'data_type': 'string',   'extra_data': {}},
        {'id': 9,  'name': 'Datenquelle',      'data_type': 'select',
         'extra_data': {'select_options': ['E-Rechnung', 'GiroCode', 'manuell']}},
    ]
    custom_tags = [
        {'id': 10, 'name': 'Eingang'},
        {'id': 11, 'name': 'Auslesen: E-Rechnung'},
        {'id': 20, 'name': 'Auslesen: nichts gefunden'},
    ]

    _register_standard_mocks(responses_lib, doc, pdf,
                              fields=custom_fields, tags=custom_tags)

    result = pipeline.run_extract(make_client(), cfg, dry_run=False)
    assert result == 0

    patch_calls = [c for c in responses_lib.calls if c.request.method == 'PATCH']
    assert len(patch_calls) == 1
    body = json.loads(patch_calls[0].request.body)
    assert 11 in body['tags']
    field_ids = [cf['field'] for cf in body['custom_fields']]
    assert 1 in field_ids   # Nummer (custom name for invoice_number)
