import io
from typing import List
from datetime import datetime, timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.models import ContentVersion, Issue

def generate_excel_issues_summary(version: ContentVersion) -> io.BytesIO:
    """
    Generates a professionally styled Excel spreadsheet (.xlsx) summarizing
    all detected issues, page numbers, categories, severities, and resolution statuses.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BrandGuard Review Summary"

    # Styling definitions
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0B3D91", end_color="0B3D91", fill_type="solid")
    title_font = Font(name="Calibri", size=16, bold=True, color="0B3D91")
    subtitle_font = Font(name="Calibri", size=10, italic=True, color="555555")

    thin_border = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD')
    )

    # Document Header metadata
    content_title = version.content.title if version.content else "Document Review"
    ws.merge_cells("A1:K1")
    ws["A1"] = f"BrandGuard AI — Document Review & Compliance Report"
    ws["A1"].font = title_font

    ws.merge_cells("A2:K2")
    ws["A2"] = f"Document: {content_title} (v{version.version_number}) | Compliance Score: {version.compliance_score}% | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    ws["A2"].font = subtitle_font

    # Column Headers
    headers = [
        "Issue ID",
        "Page #",
        "Section / Heading",
        "Category",
        "Severity",
        "Mistake Type",
        "Problematic Text",
        "Explanation & Rule Violated",
        "AI Recommended Correction",
        "Status",
        "Reviewer Comment"
    ]

    row_num = 4
    for col_num, h_text in enumerate(headers, 1):
        cell = ws.cell(row=row_num, column=col_num, value=h_text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Populate Data Rows
    issues = version.issues.all()
    for iss in issues:
        row_num += 1
        ws.cell(row=row_num, column=1, value=f"#ISS-{iss.id}").alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=2, value=iss.page_number).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=3, value=iss.section_heading or "General")
        ws.cell(row=row_num, column=4, value=iss.review_category)
        
        sev_cell = ws.cell(row=row_num, column=5, value=iss.display_severity)
        sev_cell.alignment = Alignment(horizontal="center")
        if iss.display_severity in ['Critical', 'High']:
            sev_cell.font = Font(color="B91C1C", bold=True)
        elif iss.display_severity == 'Medium':
            sev_cell.font = Font(color="B45309", bold=True)
        else:
            sev_cell.font = Font(color="1D4ED8")

        ws.cell(row=row_num, column=6, value=iss.mistake_type or "Brand Rule Violation")
        ws.cell(row=row_num, column=7, value=iss.snippet)
        ws.cell(row=row_num, column=8, value=iss.why_it_matters)
        ws.cell(row=row_num, column=9, value=iss.improved_text or iss.suggestion)
        
        status_cell = ws.cell(row=row_num, column=10, value=iss.status)
        status_cell.alignment = Alignment(horizontal="center", bold=True)
        if iss.status == 'Accepted':
            status_cell.font = Font(color="15803D", bold=True)
        elif iss.status == 'Rejected':
            status_cell.font = Font(color="B91C1C", bold=True)

        ws.cell(row=row_num, column=11, value=iss.reviewer_comment or "-")

        # Apply borders and text wrap to all cells in this row
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=c)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    # Adjust column widths
    col_widths = {1: 12, 2: 8, 3: 18, 4: 20, 5: 12, 6: 22, 7: 30, 8: 35, 9: 35, 10: 12, 11: 25}
    for c_idx, width in col_widths.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(c_idx)].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def generate_pdf_review_report(version: ContentVersion) -> io.BytesIO:
    """
    Generates a comprehensive publication-ready PDF review report using ReportLab.
    Contains document metadata, score gauge, category and severity distribution,
    and a page-referenced issue table with full AI improvement suggestions.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#0B3D91'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#555555'),
        spaceAfter=14
    )
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=colors.HexColor('#0B3D91'),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10
    )
    bold_body_style = ParagraphStyle(
        'TableBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    story = []

    # Title & Header
    content_title = version.content.title if version.content else "Document Review"
    creator_name = version.content.creator.full_name if (version.content and version.content.creator) else "Team Member"
    story.append(Paragraph(f"BrandGuard AI — Document Review Report", title_style))
    story.append(Paragraph(
        f"<b>Document:</b> {content_title} (v{version.version_number}) &nbsp;|&nbsp; "
        f"<b>Author:</b> {creator_name} &nbsp;|&nbsp; "
        f"<b>Status:</b> {version.status} &nbsp;|&nbsp; "
        f"<b>Date:</b> {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M UTC')}",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0B3D91'), spaceAfter=12))

    # Executive Summary Metrics Table
    open_crit = version.critical_issues_count
    open_high = version.high_issues_count
    open_med = version.medium_issues_count
    open_low = version.low_issues_count
    total_iss = version.total_issues_count
    compliance = version.compliance_score
    quality = version.quality_score

    summary_data = [
        [
            Paragraph(f"<b>Overall Quality Score</b><br/><font size='14' color='#0B3D91'><b>{quality}/100</b></font>", styles['Normal']),
            Paragraph(f"<b>Brand Compliance</b><br/><font size='14' color='#15803D'><b>{compliance}%</b></font>", styles['Normal']),
            Paragraph(f"<b>Total Issues</b><br/><font size='14'><b>{total_iss}</b></font>", styles['Normal']),
            Paragraph(f"<b>Critical / High</b><br/><font size='14' color='#B91C1C'><b>{open_crit + open_high}</b></font>", styles['Normal']),
            Paragraph(f"<b>Resolved / Accepted</b><br/><font size='14' color='#15803D'><b>{version.accepted_issues_count}</b></font>", styles['Normal'])
        ]
    ]

    summary_table = Table(summary_data, colWidths=[108, 108, 108, 108, 108])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # Detailed Issues Table
    story.append(Paragraph("Detailed AI Issue Detection & Improvement Log", h2_style))

    table_data = [
        [
            Paragraph("<b># / Page</b>", bold_body_style),
            Paragraph("<b>Category &amp; Type</b>", bold_body_style),
            Paragraph("<b>Severity</b>", bold_body_style),
            Paragraph("<b>Problematic Content</b>", bold_body_style),
            Paragraph("<b>Why It's Wrong &amp; AI Fix</b>", bold_body_style),
            Paragraph("<b>Status</b>", bold_body_style)
        ]
    ]

    issues = version.issues.all()
    if issues:
        for iss in issues:
            sev_color = '#B91C1C' if iss.display_severity in ['Critical', 'High'] else ('#B45309' if iss.display_severity == 'Medium' else '#1D4ED8')
            
            p_ref = f"#ISS-{iss.id}<br/>p.{iss.page_number}"
            cat_type = f"<b>{iss.review_category}</b><br/><font color='#555555'>{iss.mistake_type or '-'}</font>"
            sev_html = f"<font color='{sev_color}'><b>{iss.display_severity}</b></font>"
            snippet_html = f"<i>\"{iss.snippet[:110] + ('...' if len(iss.snippet) > 110 else '')}\"</i>"
            
            why_and_sugg = (
                f"<b>Why:</b> {iss.why_it_matters[:130]}<br/>"
                f"<b>AI Suggested Correction:</b> <font color='#15803D'>{iss.improved_text or iss.suggestion}</font>"
            )
            status_html = f"<b>{iss.status}</b>"

            table_data.append([
                Paragraph(p_ref, body_style),
                Paragraph(cat_type, body_style),
                Paragraph(sev_html, body_style),
                Paragraph(snippet_html, body_style),
                Paragraph(why_and_sugg, body_style),
                Paragraph(status_html, body_style)
            ])
    else:
        table_data.append([
            Paragraph("-", body_style),
            Paragraph("All Checks Passed", body_style),
            Paragraph("Clean", body_style),
            Paragraph("No brand or compliance violations detected.", body_style),
            Paragraph("Document meets all brand and legal standards.", body_style),
            Paragraph("Approved", body_style)
        ])

    issues_table = Table(table_data, colWidths=[45, 110, 50, 130, 160, 45])
    issues_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B3D91')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))

    story.append(issues_table)
    story.append(Spacer(1, 16))

    # Final Governance Sign-Off block
    signoff_text = (
        f"<b>Audit &amp; Human-in-the-Loop Sign-Off:</b><br/>"
        f"This document was evaluated against BrandGuard AI Governance rules. "
        f"Final publishing decisions require explicit human authorization by a designated Reviewer or Manager. "
        f"Record ID: BG-V{version.id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    )
    story.append(Paragraph(signoff_text, subtitle_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

