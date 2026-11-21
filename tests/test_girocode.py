"""Tests for parsers/girocode.py"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'parsers'))

from parsers.girocode import parse_girocode


def _make_payload(version='001', bic='VZVDDEHHXXX', iban='DE71110220330123456789',
                  amount='EUR123.45', purpose='', structured_ref='', unstructured_ref='',
                  recipient='Muster GmbH'):
    lines = [
        'BCD',
        version,
        '1',
        'SCT',
        bic,
        recipient,
        iban,
        amount,
        purpose,
        structured_ref,
        unstructured_ref,
    ]
    return '\n'.join(lines)


def test_v001_full():
    payload = _make_payload(structured_ref='RF18539007547034')
    result = parse_girocode(payload)
    assert result is not None
    assert result.iban == 'DE71110220330123456789'
    assert result.bic == 'VZVDDEHHXXX'
    assert result.recipient == 'Muster GmbH'
    assert result.amount == 'EUR123.45'
    assert result.reference == 'RF18539007547034'


def test_v002_empty_bic():
    payload = _make_payload(version='002', bic='', structured_ref='', unstructured_ref='Rechnung 42')
    result = parse_girocode(payload)
    assert result is not None
    assert result.bic is None
    assert result.reference == 'Rechnung 42'


def test_v001_no_amount():
    payload = _make_payload(amount='', structured_ref='', unstructured_ref='Test')
    result = parse_girocode(payload)
    assert result is not None
    assert result.amount is None


def test_structured_reference():
    payload = _make_payload(structured_ref='RF18539007547034', unstructured_ref='')
    result = parse_girocode(payload)
    assert result is not None
    assert result.reference == 'RF18539007547034'


def test_unstructured_reference():
    payload = _make_payload(structured_ref='', unstructured_ref='Rechnung Nr 2024-001')
    result = parse_girocode(payload)
    assert result is not None
    assert result.reference == 'Rechnung Nr 2024-001'


def test_both_references_invalid():
    payload = _make_payload(structured_ref='RF18539007547034', unstructured_ref='also here')
    result = parse_girocode(payload)
    assert result is None


def test_invalid_identifier():
    payload = _make_payload()
    payload = 'XYZ\n' + '\n'.join(payload.split('\n')[1:])
    result = parse_girocode(payload)
    assert result is None


def test_invalid_type():
    payload = _make_payload()
    lines = payload.split('\n')
    lines[3] = 'WIRE'
    result = parse_girocode('\n'.join(lines))
    assert result is None


def test_v001_missing_bic_invalid():
    # v001 requires BIC
    payload = _make_payload(version='001', bic='')
    result = parse_girocode(payload)
    assert result is None
