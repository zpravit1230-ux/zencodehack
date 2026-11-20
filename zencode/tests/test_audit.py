from app.models import db, User, Role, Content, ContentVersion, Guideline, AuditLog

def login_as(client, email, password):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

def test_every_safeguard_action_appears_in_audit_log(client, init_database, app):
    # 1. REGISTER
    client.post('/register', data={
        'full_name': 'Audit Tester',
        'email': 'auditor@lumora.demo',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)

    # 2. LOGIN
    login_as(client, 'manager@lumora.demo', 'Manager@123')

    # 3. ROLE_CHANGE
    with app.app_context():
        auditor = User.query.filter_by(email='auditor@lumora.demo').first()
        auditor_id = auditor.id

    client.post(f'/admin/users/{auditor_id}/role', data={'role_name': 'Reviewer'}, follow_redirects=True)

    # 4. UPLOAD & CHECK_RUN
    client.post('/content/new', data={
        'title': 'Audit Content Lifecycle',
        'pasted_text': 'Lumora Plus priced at Rs. 2,499 with 2 years warranty.'
    }, follow_redirects=True)

    with app.app_context():
        content = Content.query.filter_by(title='Audit Content Lifecycle').first()
        content_id = content.id

    # 5. FIX (new version upload)
    client.post(f'/content/{content_id}/version', data={
        'pasted_text': 'Lumora Plus ambient smart light for Rs. 2,499 with 2 years warranty.'
    }, follow_redirects=True)

    # 6. DECISION (standard approval)
    # Logout and log in as auditor (now Reviewer)
    client.get('/logout')
    login_as(client, 'auditor@lumora.demo', 'Password@123')

    client.post(f'/content/{content_id}/decision', data={
        'outcome': 'Approve',
        'reason': 'Approved during audit verification test.'
    }, follow_redirects=True)

    # 7. EXCEPTION
    # Upload another content item that has a serious issue to grant an exception
    client.get('/logout')
    login_as(client, 'creator@lumora.demo', 'Creator@123')
    client.post('/content/new', data={
        'title': 'Audit Exception Content',
        'pasted_text': 'Lumora Pro prototype special edition.'
    }, follow_redirects=True)

    with app.app_context():
        exc_content = Content.query.filter_by(title='Audit Exception Content').first()
        exc_id = exc_content.id

    client.get('/logout')
    login_as(client, 'manager@lumora.demo', 'Manager@123')
    client.post(f'/content/{exc_id}/decision', data={
        'outcome': 'Approve with Exception',
        'reason': 'Authorized exception for historical archive.'
    }, follow_redirects=True)

    # VERIFY AUDIT LOG ENTRIES
    with app.app_context():
        actions_in_log = [log.action for log in AuditLog.query.all()]
        print("Recorded actions:", set(actions_in_log))

        assert 'REGISTER' in actions_in_log
        assert 'LOGIN_SUCCESS' in actions_in_log
        assert 'ROLE_CHANGE' in actions_in_log
        assert 'UPLOAD' in actions_in_log
        assert 'CHECK_RUN' in actions_in_log
        assert 'FIX' in actions_in_log
        assert 'DECISION' in actions_in_log
        assert 'EXCEPTION' in actions_in_log


def test_audit_log_filters_and_reports_page(client, init_database):
    login_as(client, 'manager@lumora.demo', 'Manager@123')

    # Audit page loads with 200
    res_audit = client.get('/admin/audit')
    assert res_audit.status_code == 200
    assert b"Audit &amp; Activity Log" in res_audit.data or b"Audit & Activity Log" in res_audit.data

    # Audit filter by action
    res_filter = client.get('/admin/audit?action=LOGIN_SUCCESS')
    assert res_filter.status_code == 200
    assert b"LOGIN_SUCCESS" in res_filter.data

    # Reports page loads with 200
    res_reports = client.get('/admin/reports')
    assert res_reports.status_code == 200
    assert b"Brand Guard Compliance Reports" in res_reports.data
    assert b"Approval Rate" in res_reports.data

