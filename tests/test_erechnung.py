"""Tests for parsers/erechnung.py"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from parsers.erechnung import parse_xml


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), 'rb') as f:
        return f.read()


def test_cii_full():
    data = parse_xml(load_fixture('cii_minimal.xml'))
    assert data is not None
    assert data.source_format == 'CII'
    assert data.invoice_number == 'RE-2024-0042'
    assert data.invoice_date == '2024-03-15'
    assert data.due_date == '2024-04-15'
    assert data.amount == '123.45'
    assert data.currency == 'EUR'
    assert data.seller_name == 'Muster GmbH'
    assert data.iban == 'DE71110220330123456789'
    assert data.bic == 'VZVDDEHHXXX'
    assert data.payment_reference == 'RE-2024-0042'
    assert data.is_credit_note is False


def test_ubl_full():
    data = parse_xml(load_fixture('ubl_minimal.xml'))
    assert data is not None
    assert data.source_format == 'UBL'
    assert data.invoice_number == 'RE-2024-0099'
    assert data.invoice_date == '2024-03-15'
    assert data.due_date == '2024-04-15'
    assert data.amount == '123.45'
    assert data.currency == 'EUR'
    assert data.seller_name == 'Muster GmbH'
    assert data.iban == 'DE71110220330123456789'
    assert data.bic == 'VZVDDEHHXXX'
    assert data.payment_reference == 'RE-2024-0099'
    assert data.is_credit_note is False


def test_cii_credit_note():
    xml = load_fixture('cii_minimal.xml').replace(b'<ram:TypeCode>380</ram:TypeCode>',
                                                   b'<ram:TypeCode>381</ram:TypeCode>')
    data = parse_xml(xml)
    assert data is not None
    assert data.is_credit_note is True


def test_ubl_credit_note():
    xml = load_fixture('ubl_minimal.xml')
    # Replace Invoice root with CreditNote root
    xml = xml.replace(
        b'<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"',
        b'<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"',
    ).replace(b'</Invoice>', b'</CreditNote>')
    data = parse_xml(xml)
    assert data is not None
    assert data.is_credit_note is True
    assert data.source_format == 'UBL'


def test_cii_missing_iban():
    xml = load_fixture('cii_minimal.xml')
    # Remove IBANID element
    xml = xml.replace(b'<ram:IBANID>DE71110220330123456789</ram:IBANID>', b'')
    data = parse_xml(xml)
    assert data is not None
    assert data.iban is None


def test_ubl_missing_due_date():
    xml = load_fixture('ubl_minimal.xml')
    xml = xml.replace(b'<cbc:DueDate>2024-04-15</cbc:DueDate>', b'')
    data = parse_xml(xml)
    assert data is not None
    assert data.due_date is None


def test_invalid_xml():
    result = parse_xml(b'this is not xml at all <<<>>>')
    assert result is None


def test_non_invoice_xml():
    xml = b'<?xml version="1.0"?><root><child>value</child></root>'
    result = parse_xml(xml)
    assert result is None
