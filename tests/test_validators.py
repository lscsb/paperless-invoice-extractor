"""Tests for validators.py"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from validators import (
    validate_iban, normalize_iban, validate_amount,
    validate_date, validate_dates_consistent,
)


def test_valid_german_iban():
    assert validate_iban('DE71110220330123456789') is True


def test_invalid_checksum():
    # Flip last digit
    assert validate_iban('DE71110220330123456780') is False


def test_wrong_length():
    assert validate_iban('DE123') is False


def test_normalize_iban():
    assert normalize_iban('de71 1102 2033 0123 4567 89') == 'DE71110220330123456789'


def test_normalize_iban_already_clean():
    assert normalize_iban('DE71110220330123456789') == 'DE71110220330123456789'


def test_valid_amount():
    valid, value = validate_amount('12.34')
    assert valid is True
    assert abs(value - 12.34) < 1e-9


def test_valid_amount_no_decimals():
    valid, value = validate_amount('100')
    assert valid is True
    assert abs(value - 100.0) < 1e-9


def test_invalid_amount_negative():
    valid, value = validate_amount('-5.00')
    assert valid is False
    assert value is None


def test_invalid_amount_zero():
    valid, value = validate_amount('0.00')
    assert valid is False


def test_invalid_amount_too_many_decimals():
    valid, value = validate_amount('1.234')
    assert valid is False
    assert value is None


def test_invalid_amount_non_numeric():
    valid, value = validate_amount('abc')
    assert valid is False


def test_date_valid():
    assert validate_date('2024-01-15') is True


def test_date_invalid_month():
    assert validate_date('2024-13-01') is False


def test_date_invalid_format():
    assert validate_date('15.01.2024') is False


def test_dates_consistent():
    assert validate_dates_consistent('2024-01-01', '2024-02-01') is True


def test_dates_same_day():
    assert validate_dates_consistent('2024-01-01', '2024-01-01') is True


def test_dates_inconsistent():
    assert validate_dates_consistent('2024-02-01', '2024-01-01') is False


def test_dates_consistent_none_invoice():
    assert validate_dates_consistent(None, '2024-01-01') is True


def test_dates_consistent_none_due():
    assert validate_dates_consistent('2024-01-01', None) is True
