import os
import pytest
from PIL import Image, ImageDraw
import docx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.services.extractor import extract_text_from_file, extract_key_details, extract_dominant_colors

@pytest.fixture
def sample_files(tmp_path):
    # 1. Plain text file
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("Introducing Lumora Plus at Rs. 2,499 with 100% satisfaction guaranteed.", encoding="utf-8")

    # 2. DOCX file
    docx_path = tmp_path / "sample.docx"
    doc = docx.Document()
    doc.add_heading("Lumora Mini Launch", 0)
    doc.add_paragraph("Launch date: Oct 15, 2026. Special introductory price: Rs. 1,499.")
    doc.save(str(docx_path))

    # 3. PDF file using reportlab
    pdf_path = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(100, 750, "Lumora Smart Home Systems")
    c.drawString(100, 730, "Warranty: 2 years. Price: Rs. 2,499.")
    c.save()

    # 4. PNG file using Pillow
    png_path = tmp_path / "sample.png"
    img = Image.new('RGB', (200, 100), color='#0B3D91')
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 180, 80], fill='#F5B700')
    img.save(str(png_path))

    return {
        'txt': str(txt_path),
        'docx': str(docx_path),
        'pdf': str(pdf_path),
        'png': str(png_path)
    }

def test_extract_all_formats_without_crashing(sample_files):
    # 1. Test TXT
    txt_content, txt_type = extract_text_from_file(sample_files['txt'], "sample.txt")
    assert txt_type == 'text'
    assert "Lumora Plus" in txt_content
    assert "Rs. 2,499" in txt_content

    # 2. Test DOCX
    docx_content, docx_type = extract_text_from_file(sample_files['docx'], "sample.docx")
    assert docx_type == 'docx'
    assert "Lumora Mini" in docx_content
    assert "Rs. 1,499" in docx_content

    # 3. Test PDF
    pdf_content, pdf_type = extract_text_from_file(sample_files['pdf'], "sample.pdf")
    assert pdf_type == 'pdf'
    assert "Lumora" in pdf_content
    assert "Warranty" in pdf_content

    # 4. Test PNG (graceful OCR fallback without crash)
    png_content, png_type = extract_text_from_file(sample_files['png'], "sample.png")
    assert png_type == 'image'
    assert isinstance(png_content, str)
    assert len(png_content) > 0  # Either OCR text or graceful notice

    # 5. Test Palette dominant colors
    colors = extract_dominant_colors(sample_files['png'])
    assert len(colors) > 0
    assert any(c.startswith('#') for c in colors)

def test_extract_key_details():
    sample_text = (
        "The new Lumora Plus smart bulb is now available for Rs. 2,499. "
        "Launch event on Nov 15, 2026. "
        "We promise it is 100% guaranteed and the best in the world."
    )
    details = extract_key_details(sample_text)
    assert "Rs. 2,499" in details['prices']
    assert any("Nov 15, 2026" in d for d in details['dates'])
    assert "Lumora Plus" in details['product_names']
    assert "100%" in details['claims'] or "guaranteed" in details['claims']

