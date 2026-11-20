import re
from app import create_app
from app.config import Config
from app.models import db, User, Content, Guideline, AuditLog

def test_all_four_demo_logins_and_populated_pages():
    # Use real SQLite database populated by seed.py
    app = create_app(Config)
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    demo_creds = [
        ('manager@lumora.demo', 'Manager@123', '/dashboard/manager', b"Brand Operations Dashboard"),
        ('reviewer@lumora.demo', 'Reviewer@123', '/dashboard/reviewer', b"Reviewer Queue"),
        ('priya@lumora.demo', 'Creator@123', '/dashboard/creator', b"Creator Workspace"),
        ('arjun@lumora.demo', 'Creator@123', '/dashboard/creator', b"Creator Workspace")
    ]

    for email, password, target_path, expected_header in demo_creds:
        login_res = client.post('/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)
        assert login_res.status_code == 200, f"Login failed for {email}"
        assert expected_header in login_res.data, f"Header not found for {email} on {target_path}"

        # Verify page is populated with data
        if 'manager' in email:
            # Check guidelines and audit counts
            res_guidelines = client.get('/guidelines/')
            assert res_guidelines.status_code == 200
            assert b"Lumora Plus" in res_guidelines.data
            assert b"Lumora Pro" in res_guidelines.data

            res_audit = client.get('/admin/audit')
            assert res_audit.status_code == 200
            assert b"Event History" in res_audit.data

            res_reports = client.get('/admin/reports')
            assert res_reports.status_code == 200
            assert b"Issues by Brand Category" in res_reports.data

        client.get('/logout')

    # Verify login page displays Demo accounts card
    login_page = client.get('/login')
    assert login_page.status_code == 200
    assert b"Demo Accounts" in login_page.data
    assert b"manager@lumora.demo" in login_page.data
    assert b"reviewer@lumora.demo" in login_page.data
    assert b"priya@lumora.demo" in login_page.data
    assert b"arjun@lumora.demo" in login_page.data
