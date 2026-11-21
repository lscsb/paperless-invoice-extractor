"""Integration tests: programmatically generated test PDFs."""

import io
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), 'rb') as f:
        return f.read()


def make_pdf_with_attachment(filename: str, data: bytes) -> bytes:
    """Create a minimal PDF with one embedded file attachment."""
    import pypdf

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_attachment(filename, data)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_pdf_with_qr_image(qr_text: str) -> bytes:
    """Create a PDF page containing a rendered QR code image."""
    import segno
    from fpdf import FPDF

    qr = segno.make(qr_text, error='M')
    png_buf = io.BytesIO()
    qr.save(png_buf, kind='png', scale=5)
    png_buf.seek(0)

    pdf = FPDF()
    pdf.add_page()
    # fpdf2 accepts file-like objects or paths; write to temp file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp.write(png_buf.getvalue())
        tmp_path = tmp.name
    try:
        pdf.image(tmp_path, x=50, y=50, w=100)
    finally:
        os.unlink(tmp_path)

    return pdf.output()


def test_pdf_with_embedded_cii():
    """Embed CII XML as attachment, extract via pdf_utils, parse → verify fields."""
    from pdf_utils import extract_embedded_xmls
    from parsers.erechnung import parse_xml

    xml_bytes = load_fixture('cii_minimal.xml')
    pdf_bytes = make_pdf_with_attachment('factur-x.xml', xml_bytes)

    xmls = extract_embedded_xmls(pdf_bytes)
    assert len(xmls) == 1
    filename, content = xmls[0]
    assert filename.lower().endswith('.xml')

    data = parse_xml(content)
    assert data is not None
    assert data.invoice_number == 'RE-2024-0042'
    assert data.iban == 'DE71110220330123456789'
    assert data.amount == '123.45'


def test_pdf_with_girocode():
    """Create PDF with rendered GiroCode QR, decode, parse → verify fields."""
    from pdf_utils import render_pages_as_images

    girocode_text = '\n'.join([
        'BCD',
        '001',
        '1',
        'SCT',
        'VZVDDEHHXXX',
        'Muster GmbH',
        'DE71110220330123456789',
        'EUR99.00',
        '',
        '',
        'Rechnung 2024-001',
    ])

    pdf_bytes = make_pdf_with_qr_image(girocode_text)

    from pyzbar.pyzbar import decode as pyzbar_decode, ZBarSymbol

    images = render_pages_as_images(pdf_bytes, max_pages=1, dpi=300)
    assert len(images) >= 1

    decoded = pyzbar_decode(images[0], symbols=[ZBarSymbol.QRCODE])
    assert len(decoded) >= 1

    from parsers.girocode import parse_girocode

    text = decoded[0].data.decode('utf-8')
    result = parse_girocode(text)
    assert result is not None
    assert result.iban == 'DE71110220330123456789'
    assert result.recipient == 'Muster GmbH'
    assert result.reference == 'Rechnung 2024-001'
