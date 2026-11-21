"""Validators for IBAN, amounts, and dates."""

from datetime import date


IBAN_LENGTHS = {
    'AT': 20, 'BE': 16, 'CH': 21, 'CZ': 24, 'DE': 22, 'DK': 18,
    'ES': 24, 'FI': 18, 'FR': 27, 'GB': 22, 'IT': 27, 'LU': 20,
    'NL': 18, 'NO': 15, 'PL': 28, 'PT': 25, 'SE': 24, 'SK': 24,
}


def normalize_iban(iban: str) -> str:
    """Remove spaces and uppercase."""
    return iban.replace(' ', '').upper()


def validate_iban(iban: str) -> bool:
    """Validate IBAN via mod-97 checksum."""
    iban = normalize_iban(iban)
    country = iban[:2]
    if country not in IBAN_LENGTHS:
        return False
    if len(iban) != IBAN_LENGTHS[country]:
        return False
    # Rearrange: move first 4 chars to end
    rearranged = iban[4:] + iban[:4]
    # Letters → digits: A=10..Z=35
    numeric = ''.join(str(ord(c) - ord('A') + 10) if c.isalpha() else c for c in rearranged)
    return int(numeric) % 97 == 1


def validate_amount(amount_str: str) -> tuple[bool, float | None]:
    """Return (valid, value_as_float). Must be positive decimal, max 2 decimal places."""
    try:
        value = float(amount_str)
    except (ValueError, TypeError):
        return False, None
    if value <= 0:
        return False, None
    # Check decimal places
    if '.' in amount_str:
        decimals = amount_str.split('.')[1]
        if len(decimals) > 2:
            return False, None
    return True, value


def validate_date(date_str: str) -> bool:
    """Accept YYYY-MM-DD format."""
    try:
        date.fromisoformat(date_str)
        return True
    except (ValueError, TypeError):
        return False


def validate_dates_consistent(invoice_date: str | None, due_date: str | None) -> bool:
    """due_date must not be before invoice_date."""
    if invoice_date is None or due_date is None:
        return True
    try:
        inv = date.fromisoformat(invoice_date)
        due = date.fromisoformat(due_date)
        return due >= inv
    except (ValueError, TypeError):
        return False
