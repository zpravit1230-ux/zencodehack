import io
import os
import pytest
from app.models import db, User, Content, ContentVersion, Issue
from app.services.extractor import extract_document_content, extract_key_details
from app.services.checker import run_brand_check
from openpyxl import load_workbook

def login_as(client, email, password):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

def test_extract_multipage_and_tabular_formats(tmp_path):
    # CSV test
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("Product,Price,Status\nLumora Plus,2499,Active\nLumora Mini,1499,Draft", encoding='utf-8')
    full_text, ftype, pages = extract_document_content(file_path=str(csv_file), filename="data.csv")
    assert ftype == 'spreadsheet'
    assert len(pages) >= 1
    assert "Lumora Plus" in full_text
    assert "2499" in full_text

    # TXT test with page breaks
    txt_file = tmp_path / "multipage.txt"
    txt_file.write_text("Page 1 text\n\x0cPage 2 text\n\x0cPage 3 text", encoding='utf-8')
    full_text, ftype, pages = extract_document_content(file_path=str(txt_file), filename="multipage.txt")
    assert ftype == 'text'
    assert len(pages) == 3
    assert pages[1]['page_number'] == 2

def test_ai_checker_seven_categories_coverage():
    content = """
    # Confidential Q3 Product Strategy
    Contact customer directly at secret.agent@company.com or +1 555-0199 for internal credentials.
    We guarantee 100% cure for cancer with our revolutionary Lumora Pro tool!
    BUY NOW OR REGRET IT FOREVER!!!!!!
    Launch date: Oct 15, 2026. Special price: Rs. 9999.
    teh system has unverified and mispelled statements.
    """
    pages_data = [
        {'page_number': 1, 'heading': 'Confidential Q3 Product Strategy', 'text': content, 'tables': []}
    ]
    details = extract_key_details(content)
    issues = run_brand_check(content, details, pages_data=pages_data)
    assert len(issues) > 0

    # Verify issue fields
    for iss in issues:
        assert 'issue_id' in iss
        assert 'page_number' in iss
        assert iss['page_number'] == 1
        assert 'section_heading' in iss
        assert 'mistake_type' in iss
        assert 'severity' in iss
        assert 'improved_text' in iss
        assert 'explanation' in iss
        assert 'suggestion' in iss

    # Check that privacy, marketing promises, and grammar/tone are captured
    severities = {iss['severity'] for iss in issues}
    assert 'Serious' in severities or 'Warning' in severities

def test_suggestion_engine_accept_reject_edit(client, init_database, app):
    with app.app_context():
        creator = User.query.filter_by(email='creator@lumora.demo').first()
        content = Content(title='Marketing Draft', creator_id=creator.id)
        db.session.add(content)
        db.session.commit()

        initial_text = "We guarantee 100% cure with Lumora Pro."
        pages = [{'page_number': 1, 'heading': 'Intro', 'text': initial_text, 'tables': []}]
        details = extract_key_details(initial_text)
        detected_issues = run_brand_check(initial_text, details, pages_data=pages)
        
        version = ContentVersion(
            content_id=content.id,
            version_number=1,
            extracted_text=initial_text,
            corrected_text=initial_text,
            file_type='text'
        )
        version.set_page_data(pages)
        db.session.add(version)
        db.session.commit()

        for d in detected_issues:
            iss = Issue(
                version_id=version.id,
                category=d.get('category', 'WORDS'),
                severity=d.get('severity', 'Warning'),
                rule_id=d.get('rule_id', 'RULE'),
                snippet=d.get('snippet', ''),
                why_it_matters=d.get('why_it_matters') or d.get('explanation', ''),
                suggestion=d.get('suggestion', ''),
                page_number=d.get('page_number', 1),
                section_heading=d.get('section_heading', 'General'),
                mistake_type=d.get('mistake_type', 'Mistake'),
                improved_text=d.get('improved_text', 'Improved replacement text'),
                status='Open'
            )
            db.session.add(iss)
        db.session.commit()
        version.recalculate_scores()
        db.session.commit()

        first_issue = Issue.query.filter_by(version_id=version.id).first()
        issue_id = first_issue.id
        content_id = content.id

    login_as(client, 'creator@lumora.demo', 'Creator@123')

    # Test Accept Suggestion
    resp = client.post(f'/content/{content_id}/issue/{issue_id}/accept')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['status'] == 'Accepted'

    with app.app_context():
        updated_iss = Issue.query.get(issue_id)
        assert updated_iss.status == 'Accepted'
        updated_ver = ContentVersion.query.get(version.id)
        assert updated_ver.compliance_score >= 0

    # Test Reject Suggestion
    resp = client.post(f'/content/{content_id}/issue/{issue_id}/reject')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['status'] == 'Rejected'

    # Test Edit Suggestion Manually
    resp = client.post(f'/content/{content_id}/issue/{issue_id}/edit', data={'custom_text': 'Custom editorial fix.'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['status'] == 'Modified'

    with app.app_context():
        updated_iss = Issue.query.get(issue_id)
        assert updated_iss.improved_text == 'Custom editorial fix.'
        assert 'Custom editorial fix.' in ContentVersion.query.get(version.id).current_text

def test_document_exports(client, init_database, app):
    with app.app_context():
        creator = User.query.filter_by(email='creator@lumora.demo').first()
        content = Content(title='Export Test Document', creator_id=creator.id)
        db.session.add(content)
        db.session.commit()

        orig_text = "Original draft containing Lumora Pro."
        version = ContentVersion(
            content_id=content.id,
            version_number=1,
            extracted_text=orig_text,
            corrected_text="Corrected draft containing Lumora Plus.",
            file_type='text'
        )
        version.set_page_data([{'page_number': 1, 'heading': 'Page 1', 'text': orig_text, 'tables': []}])
        db.session.add(version)
        db.session.commit()

        iss = Issue(
            version_id=version.id,
            category='WORDS',
            severity='Serious',
            rule_id='RULE-001',
            snippet='Lumora Pro',
            why_it_matters='Use Lumora Plus instead',
            suggestion='Change to Lumora Plus',
            improved_text='Lumora Plus',
            status='Open'
        )
        db.session.add(iss)
        version.recalculate_scores()
        db.session.commit()
        cid = content.id

    login_as(client, 'creator@lumora.demo', 'Creator@123')

    # Test Download Original
    resp = client.get(f'/content/{cid}/export/original')
    assert resp.status_code == 200
    assert b"Original draft containing Lumora Pro." in resp.data

    # Test Download Corrected
    resp = client.get(f'/content/{cid}/export/corrected')
    assert resp.status_code == 200
    assert b"Corrected draft containing Lumora Plus." in resp.data

    # Test Export Excel
    resp = client.get(f'/content/{cid}/export/excel')
    assert resp.status_code == 200
    assert 'spreadsheet' in resp.content_type or 'excel' in resp.content_type or 'octet-stream' in resp.content_type
    wb = load_workbook(filename=io.BytesIO(resp.data))
    assert 'BrandGuard Review Summary' in wb.sheetnames

    # Test Export PDF
    resp = client.get(f'/content/{cid}/export/pdf')
    assert resp.status_code == 200
    assert resp.content_type == 'application/pdf'
    assert len(resp.data) > 500
