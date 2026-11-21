"""GiroCode / EPC QR code parser."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GiroCodeData:
    bic: Optional[str]
    recipient: str
    iban: str
    amount: Optional[str]          # e.g. 'EUR12.34'
    purpose_code: Optional[str]
    reference: Optional[str]       # structured (starts RF) or unstructured text


def parse_girocode(text: str) -> Optional[GiroCodeData]:
    """Parse a GiroCode text payload."""
    lines = text.splitlines()

    # Minimum required lines: 0..10 (11), line 11 is optional
    if len(lines) < 10:
        return None

    # Line 0: must be 'BCD'
    if lines[0].strip() != 'BCD':
        return None

    # Line 1: version
    version = lines[1].strip()
    if version not in ('001', '002'):
        return None

    # Line 2: charset (only 1=UTF-8 supported, but don't reject others)
    # Line 3: must be 'SCT'
    if lines[3].strip() != 'SCT':
        return None

    bic = lines[4].strip() or None
    if bic is None and version == '001':
        return None  # BIC required in v001

    recipient = lines[5].strip()
    if not recipient:
        return None

    iban = lines[6].strip()
    if not iban:
        return None

    amount_raw = lines[7].strip() or None
    purpose_code = lines[8].strip() or None

    structured_ref = lines[9].strip() if len(lines) > 9 else ''
    unstructured_ref = lines[10].strip() if len(lines) > 10 else ''

    # At most one of structured / unstructured may be non-empty
    if structured_ref and unstructured_ref:
        return None

    reference = structured_ref or unstructured_ref or None

    return GiroCodeData(
        bic=bic,
        recipient=recipient,
        iban=iban,
        amount=amount_raw,
        purpose_code=purpose_code,
        reference=reference,
    )
