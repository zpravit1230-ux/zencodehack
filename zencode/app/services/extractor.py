import os
import re
import csv
from typing import Tuple, Dict, Any, List, Optional
from PIL import Image

# Document parsers with graceful fallbacks
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import docx
except ImportError:
    docx = None

try:
    import pptx
except ImportError:
    pptx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import pytesseract
except ImportError:
    pytesseract = None


def extract_text_from_file(file_path: str, filename: str) -> Tuple[str, str]:
    """
    Backward-compatible extractor. Extracts full plain text and file_type string.
    """
    text, file_type, _ = extract_document_content(file_path=file_path, filename=filename)
    return text, file_type


def extract_document_content(
    file_path: Optional[str] = None,
    filename: Optional[str] = None,
    pasted_text: Optional[str] = None
) -> Tuple[str, str, List[Dict[str, Any]]]:
    """
    Comprehensive multi-format document parser.
    Extracts complete text, document type, and page-by-page structured content.
    Returns: (full_text, file_type, page_data_list)
    where page_data_list = [{'page_number': int, 'heading': str, 'text': str, 'tables': list}]
    """
    # 1. Handle pasted text
    if not file_path and pasted_text:
        full_text, pages = _extract_raw_text_pages(pasted_text, title="Pasted Text Content")
        return full_text, 'text', pages

    if not file_path or not os.path.exists(file_path):
        raw = (pasted_text or "").strip()
        full_text, pages = _extract_raw_text_pages(raw, title="Empty Content")
        return full_text, 'text', pages

    fname = filename or os.path.basename(file_path)
    ext = os.path.splitext(fname)[1].lower().lstrip('.')

    # 2. Dispatch according to extension
    if ext == 'pdf':
        full_text, pages = _extract_pdf_pages(file_path)
        return full_text, 'pdf', pages
    elif ext in ['docx', 'doc']:
        full_text, pages = _extract_docx_pages(file_path)
        return full_text, 'docx', pages
    elif ext in ['pptx', 'ppt']:
        full_text, pages = _extract_pptx_pages(file_path)
        return full_text, 'presentation', pages
    elif ext in ['xlsx', 'xls']:
        full_text, pages = _extract_xlsx_pages(file_path)
        return full_text, 'spreadsheet', pages
    elif ext == 'csv':
        full_text, pages = _extract_csv_pages(file_path)
        return full_text, 'spreadsheet', pages
    elif ext in ['png', 'jpg', 'jpeg', 'webp']:
        full_text, pages = _extract_image_pages(file_path)
        return full_text, 'image', pages
    elif ext == 'txt':
        full_text, pages = _extract_txt_file_pages(file_path)
        return full_text, 'text', pages
    else:
        # Generic text fallback
        try:
            full_text, pages = _extract_txt_file_pages(file_path)
            return full_text, 'text', pages
        except Exception:
            err_msg = f"[Unsupported file format: .{ext}]"
            return err_msg, 'unknown', [{'page_number': 1, 'heading': 'File', 'text': err_msg, 'tables': []}]


# ---------------------------------------------------------------------------
# Format Extractors
# ---------------------------------------------------------------------------

def _extract_pdf_pages(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    pages = []
    full_text_list = []

    if not pdfplumber:
        err = "[PDF reader (pdfplumber) is not available]"
        return err, [{'page_number': 1, 'heading': 'Page 1', 'text': err, 'tables': []}]

    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                tables = []
                
                # Extract tables on this page
                raw_tables = page.extract_tables() or []
                for t in raw_tables:
                    clean_t = [
                        [str(cell or "").strip() for cell in row]
                        for row in t if any(row)
                    ]
                    if clean_t:
                        tables.append(clean_t)

                # Format tables as text lines if present
                table_lines = []
                for t in tables:
                    for r in t:
                        table_lines.append(" | ".join(r))

                combined_page_text = page_text.strip()
                if table_lines:
                    combined_page_text += "\n\n[Table Data]:\n" + "\n".join(table_lines)

                # OCR fallback for blank/scanned page
                if not combined_page_text.strip() and pytesseract:
                    try:
                        pil_img = page.to_image(resolution=150).original
                        ocr_res = pytesseract.image_to_string(pil_img).strip()
                        if ocr_res:
                            combined_page_text = f"[OCR Scanned Content]:\n{ocr_res}"
                    except Exception:
                        pass

                if not combined_page_text.strip():
                    combined_page_text = f"[Page {page_num}: No selectable text or scanned graphical content]"

                pages.append({
                    'page_number': page_num,
                    'heading': f"Page {page_num}",
                    'text': combined_page_text,
                    'tables': tables
                })
                full_text_list.append(combined_page_text)

        full_text = "\n\n".join(full_text_list).strip()
        return (full_text if full_text else "[PDF file contained no readable text]", pages)
    except Exception as e:
        err = f"[Error parsing PDF: {str(e)}]"
        return err, [{'page_number': 1, 'heading': 'Page 1', 'text': err, 'tables': []}]


def _extract_docx_pages(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    pages = []
    full_text_list = []

    if not docx:
        err = "[DOCX reader (python-docx) is not available]"
        return err, [{'page_number': 1, 'heading': 'Section 1', 'text': err, 'tables': []}]

    try:
        doc = docx.Document(file_path)
        all_elements = []

        # Extract paragraphs with heading detection
        current_heading = "Document Content"
        current_paragraphs = []
        page_index = 1

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            # Check if this paragraph is a heading
            if p.style and ('Heading' in p.style.name or 'Title' in p.style.name):
                if current_paragraphs:
                    section_text = "\n\n".join(current_paragraphs)
                    pages.append({
                        'page_number': page_index,
                        'heading': current_heading,
                        'text': section_text,
                        'tables': []
                    })
                    full_text_list.append(section_text)
                    page_index += 1
                    current_paragraphs = []
                current_heading = text
            else:
                current_paragraphs.append(text)

        # Extract tables
        tables_data = []
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                row_vals = [cell.text.strip() for cell in row.cells]
                if any(row_vals):
                    table_rows.append(row_vals)
            if table_rows:
                tables_data.append(table_rows)
                formatted_tbl = "\n".join(" | ".join(r) for r in table_rows)
                current_paragraphs.append(f"[Table Data]:\n{formatted_tbl}")

        # Flush remaining section
        if current_paragraphs or not pages:
            section_text = "\n\n".join(current_paragraphs) if current_paragraphs else "[Empty Document]"
            pages.append({
                'page_number': page_index,
                'heading': current_heading,
                'text': section_text,
                'tables': tables_data
            })
            full_text_list.append(section_text)

        full_text = "\n\n".join(full_text_list).strip()
        return full_text, pages
    except Exception as e:
        err = f"[Error parsing DOCX: {str(e)}]"
        return err, [{'page_number': 1, 'heading': 'Section 1', 'text': err, 'tables': []}]


def _extract_pptx_pages(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    pages = []
    full_text_list = []

    if not pptx:
        err = "[Presentation reader (python-pptx) is not available]"
        return err, [{'page_number': 1, 'heading': 'Slide 1', 'text': err, 'tables': []}]

    try:
        prs = pptx.Presentation(file_path)
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_title = f"Slide {slide_num}"
            slide_texts = []
            slide_tables = []

            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        p_txt = paragraph.text.strip()
                        if p_txt:
                            if shape == slide.shapes.title and not slide_texts:
                                slide_title = p_txt
                            else:
                                slide_texts.append(p_txt)
                elif shape.has_table:
                    tbl = shape.table
                    tbl_rows = []
                    for row in tbl.rows:
                        row_vals = [cell.text.strip() for cell in row.cells]
                        if any(row_vals):
                            tbl_rows.append(row_vals)
                    if tbl_rows:
                        slide_tables.append(tbl_rows)
                        slide_texts.append("\n".join(" | ".join(r) for r in tbl_rows))

            slide_body = "\n".join(slide_texts) if slide_texts else f"[Slide {slide_num}: Visual / Graphic Layout]"
            full_slide_content = f"### {slide_title}\n{slide_body}"

            pages.append({
                'page_number': slide_num,
                'heading': slide_title,
                'text': full_slide_content,
                'tables': slide_tables
            })
            full_text_list.append(full_slide_content)

        full_text = "\n\n".join(full_text_list).strip()
        return (full_text if full_text else "[Presentation contained no text shapes]", pages)
    except Exception as e:
        err = f"[Error parsing Presentation: {str(e)}]"
        return err, [{'page_number': 1, 'heading': 'Slide 1', 'text': err, 'tables': []}]


def _extract_xlsx_pages(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    pages = []
    full_text_list = []

    if not openpyxl:
        err = "[Spreadsheet reader (openpyxl) is not available]"
        return err, [{'page_number': 1, 'heading': 'Sheet 1', 'text': err, 'tables': []}]

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        for sheet_num, sheet_name in enumerate(wb.sheetnames, 1):
            ws = wb[sheet_name]
            sheet_rows = []
            for row in ws.iter_rows(values_only=True):
                # Filter out completely empty rows
                row_vals = [str(v).strip() if v is not None else "" for v in row]
                if any(row_vals):
                    sheet_rows.append(row_vals)

            formatted_rows = [" | ".join(r) for r in sheet_rows]
            sheet_text = f"### Sheet: {sheet_name}\n" + ("\n".join(formatted_rows) if formatted_rows else "[Empty Sheet]")

            pages.append({
                'page_number': sheet_num,
                'heading': f"Sheet: {sheet_name}",
                'text': sheet_text,
                'tables': [sheet_rows] if sheet_rows else []
            })
            full_text_list.append(sheet_text)

        full_text = "\n\n".join(full_text_list).strip()
        return (full_text if full_text else "[Spreadsheet contained no data]", pages)
    except Exception as e:
        err = f"[Error parsing Spreadsheet: {str(e)}]"
        return err, [{'page_number': 1, 'heading': 'Sheet 1', 'text': err, 'tables': []}]


def _extract_csv_pages(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    pages = []
    rows = []
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                reader = csv.reader(f)
                rows = [r for r in reader if any(r)]
            break
        except Exception:
            continue

    if not rows:
        return "[Empty or unreadable CSV file]", [{'page_number': 1, 'heading': 'CSV Data', 'text': "[Empty CSV]", 'tables': []}]

    # Chunk into pages of 30 rows
    chunk_size = 30
    full_text_list = []

    for idx in range(0, len(rows), chunk_size):
        chunk = rows[idx:idx + chunk_size]
        page_num = (idx // chunk_size) + 1
        formatted = "\n".join(" | ".join(r) for r in chunk)
        title = f"CSV Records ({idx + 1} - {min(idx + chunk_size, len(rows))})"
        content = f"### {title}\n{formatted}"

        pages.append({
            'page_number': page_num,
            'heading': title,
            'text': content,
            'tables': [chunk]
        })
        full_text_list.append(content)

    full_text = "\n\n".join(full_text_list).strip()
    return full_text, pages


def _extract_image_pages(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    ocr_text = ""
    width, height = 0, 0
    try:
        img = Image.open(file_path)
        width, height = img.width, img.height
        if pytesseract:
            try:
                ocr_text = pytesseract.image_to_string(img).strip()
            except Exception:
                ocr_text = f"[Image OCR Notice: Optical character recognition engine unavailable. Dimensions: {width}x{height}px]"
        else:
            ocr_text = f"[Image OCR Notice: pytesseract library unavailable. Dimensions: {width}x{height}px]"
    except Exception as e:
        ocr_text = f"[Error reading image file: {str(e)}]"

    full_text = f"[Visual Image Asset - {width}x{height}px]\n{ocr_text}"
    pages = [{
        'page_number': 1,
        'heading': f"Visual Image ({width}x{height}px)",
        'text': full_text,
        'tables': []
    }]
    return full_text, pages


def _extract_txt_file_pages(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    raw_text = ""
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                raw_text = f.read().strip()
            break
        except UnicodeDecodeError:
            continue
    if not raw_text:
        try:
            with open(file_path, 'rb') as f:
                raw_text = f.read().decode('ascii', errors='replace').strip()
        except Exception:
            raw_text = ""

    return _extract_raw_text_pages(raw_text, title=os.path.basename(file_path))


def _extract_raw_text_pages(text: str, title: str = "Document Text") -> Tuple[str, List[Dict[str, Any]]]:
    clean_text = (text or "").strip()
    if not clean_text:
        return "", [{'page_number': 1, 'heading': title, 'text': "", 'tables': []}]

    # Chunk into pages of ~250-350 words, preserving paragraph boundaries
    paragraphs = [p.strip() for p in clean_text.split('\n\n') if p.strip()]
    if not paragraphs:
        paragraphs = [clean_text]

    pages = []
    current_page_paras = []
    current_word_count = 0
    page_num = 1

    for para in paragraphs:
        w_cnt = len(para.split())
        if current_word_count + w_cnt > 320 and current_page_paras:
            p_text = "\n\n".join(current_page_paras)
            heading = f"Page {page_num}" if len(paragraphs) > 2 else title
            pages.append({
                'page_number': page_num,
                'heading': heading,
                'text': p_text,
                'tables': []
            })
            page_num += 1
            current_page_paras = [para]
            current_word_count = w_cnt
        else:
            current_page_paras.append(para)
            current_word_count += w_cnt

    if current_page_paras:
        p_text = "\n\n".join(current_page_paras)
        heading = f"Page {page_num}" if page_num > 1 else title
        pages.append({
            'page_number': page_num,
            'heading': heading,
            'text': p_text,
            'tables': []
        })

    return clean_text, pages


# ---------------------------------------------------------------------------
# Dominant Colors & Key Details Extractor
# ---------------------------------------------------------------------------

def extract_dominant_colors(file_path: str, max_colors: int = 5) -> List[str]:
    """
    Extracts dominant HEX colors from an image file using Pillow.
    """
    try:
        img = Image.open(file_path).convert('RGB')
        img = img.resize((150, 150))
        quantized = img.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()
        color_counts = quantized.getcolors()

        if not color_counts or not palette:
            return []

        sorted_colors = sorted(color_counts, key=lambda x: x[0], reverse=True)
        dominant_hex = []

        for count, idx in sorted_colors[:max_colors]:
            r = palette[idx * 3]
            g = palette[idx * 3 + 1]
            b = palette[idx * 3 + 2]
            hex_code = f"#{r:02X}{g:02X}{b:02X}"
            dominant_hex.append(hex_code)

        return dominant_hex
    except Exception as e:
        print(f"Palette extraction error: {e}")
        return []


def extract_key_details(text: str, file_path: str = None) -> Dict[str, Any]:
    """
    Extracts structured key details: prices, dates, product names, claims, and dominant colors.
    """
    details: Dict[str, Any] = {
        'prices': [],
        'dates': [],
        'product_names': [],
        'claims': [],
        'dominant_colors': []
    }

    if not text:
        text = ""

    # Prices
    price_pattern = r'(?:Rs\.?|₹|INR|\$)\s*[\d,]+(?:\.\d{2})?'
    prices = re.findall(price_pattern, text, re.IGNORECASE)
    details['prices'] = list(dict.fromkeys([p.strip() for p in prices]))

    # Dates
    date_patterns = [
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\b',
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b(?:Q[1-4]\s+\d{4}|\d{4}-\d{2}-\d{2})\b'
    ]
    dates = []
    for pat in date_patterns:
        dates.extend(re.findall(pat, text, re.IGNORECASE))
    details['dates'] = list(dict.fromkeys([d.strip() for d in dates]))

    # Product names
    product_pattern = r'\bLumora\s+[A-Za-z0-9+]+\b'
    products = re.findall(product_pattern, text, re.IGNORECASE)
    details['product_names'] = list(dict.fromkeys([p.strip() for p in products]))

    # Claims
    claim_terms = [
        'guaranteed', '100% satisfaction', '100%', 'best in the world',
        'no risk', 'cure', 'permanent', 'never fail', 'miracle', 'zero defect'
    ]
    found_claims = []
    text_lower = text.lower()
    for term in claim_terms:
        if term in text_lower:
            found_claims.append(term)
    details['claims'] = list(dict.fromkeys(found_claims))

    # Dominant colors
    if file_path and os.path.exists(file_path):
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        if ext in ['png', 'jpg', 'jpeg', 'webp']:
            details['dominant_colors'] = extract_dominant_colors(file_path)

    return details
