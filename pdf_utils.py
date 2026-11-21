"""PDF utilities: embedded file extraction and page rendering."""

import io


def extract_embedded_xmls(pdf_bytes: bytes) -> list[tuple[str, bytes]]:
    """Return [(filename, content), ...] for all embedded XML files."""
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    results = []

    attachments = reader.attachments  # dict: {filename: [bytes, ...]}
    for filename, data_list in attachments.items():
        if filename.lower().endswith('.xml'):
            for data in data_list:
                if data:
                    results.append((filename, data))

    return results


def render_pages_as_images(pdf_bytes: bytes, max_pages: int = 3, dpi: int = 300) -> list:
    """Return list of PIL Images for first max_pages pages using pypdfium2."""
    import pypdfium2

    pdf = pypdfium2.PdfDocument(bytes(pdf_bytes))
    images = []
    scale = dpi / 72

    for i in range(min(max_pages, len(pdf))):
        page = pdf.get_page(i)
        bitmap = page.render(scale=scale)
        images.append(bitmap.to_pil())
        page.close()

    pdf.close()
    return images
