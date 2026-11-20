import pytest
from app.models import db, User, Role, Content, ContentVersion, Issue, Decision, Guideline, AuditLog

def login_as(client, email, password):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

def setup_test_rules(app):
    with app.app_context():
        g1 = Guideline(type='WORDS', key='Lumora Pro', value='Lumora Plus', description='Prototype name', active=True)
        g2 = Guideline(type='DETAILS', key='Price - Lumora Plus', value='Rs. 2,499', description='MSRP', active=True)
        g3 = Guideline(type='PROMISES', key='100% guaranteed', value='Standard reliability', description='Risky claim', active=True)
        db.session.add_all([g1, g2, g3])
        db.session.commit()

def create_sample_flyer(client, app, title='Test Flyer', text='Buy Lumora Pro for Rs. 1,999 today!'):
    setup_test_rules(app)
    login_as(client, 'creator@lumora.demo', 'Creator@123')
    client.post('/content/new', data={
        'title': title,
        'pasted_text': text
    }, follow_redirects=True)
    client.get('/logout')
    with app.app_context():
        c = Content.query.filter_by(title=title).first()
        return c.id


# SAFEGUARD 1: Content with open Serious issue cannot be approved
def test_serious_issue_blocks_approval(client, init_database, app):
    content_id = create_sample_flyer(client, app)

    # Reviewer tries to approve -> Blocked by safeguard!
    login_as(client, 'reviewer@lumora.demo', 'Reviewer@123')
    res_decide = client.post(f'/content/{content_id}/decision', data={
        'outcome': 'Approve',
        'reason': 'Looks fine to me'
    }, follow_redirects=True)

    assert b"Safeguard Violation: Content with open Serious brand issues cannot be approved." in res_decide.data

    with app.app_context():
        content = db.session.get(Content, content_id)
        v1 = content.latest_version
        assert v1.status != 'Approved'
        # Check audit log blocked attempt
        audit = AuditLog.query.filter_by(action='APPROVAL_BLOCKED_SERIOUS_ISSUES').first()
        assert audit is not None


# SAFEGUARD 2: Approval with exception requires mandatory written reason
def test_exception_requires_mandatory_reason(client, init_database, app):
    content_id = create_sample_flyer(client, app)

    login_as(client, 'reviewer@lumora.demo', 'Reviewer@123')

    # Attempt Approve with Exception with EMPTY reason -> Blocked!
    res_no_reason = client.post(f'/content/{content_id}/decision', data={
        'outcome': 'Approve with Exception',
        'reason': ''
    }, follow_redirects=True)
    assert b"Safeguard Violation: A written justification reason is mandatory when approving with an exception." in res_no_reason.data

    # Attempt with valid written reason -> Succeeded!
    res_with_reason = client.post(f'/content/{content_id}/decision', data={
        'outcome': 'Approve with Exception',
        'reason': 'Executive approval granted for limited legacy distributor clearance.'
    }, follow_redirects=True)
    assert b"Decision recorded" in res_with_reason.data
    assert b"Approve with Exception" in res_with_reason.data

    with app.app_context():
        v = db.session.get(Content, content_id).latest_version
        assert v.status == 'Approved with Exception'
        assert v.decision.is_exception is True
        assert "distributor clearance" in v.decision.reason

        audit = AuditLog.query.filter_by(action='EXCEPTION').first()
        assert audit is not None


# SAFEGUARD 3: Re-check automatically on every new version
def test_recheck_on_new_version(client, init_database, app):
    content_id = create_sample_flyer(client, app)

    # Creator uploads fixed version (v2)
    login_as(client, 'creator@lumora.demo', 'Creator@123')

    res_v2 = client.post(f'/content/{content_id}/version', data={
        'pasted_text': 'Buy the brand new Lumora Plus for Rs. 2,499 today.'
    }, follow_redirects=True)
    assert res_v2.status_code == 200
    assert b"Version 2 uploaded and re-checked automatically." in res_v2.data

    with app.app_context():
        c = db.session.get(Content, content_id)
        v2 = c.latest_version
        assert v2.version_number == 2
        # Fixed copy has no serious issues, so status is Waiting for Review
        assert v2.serious_issues_count == 0
        assert v2.status == 'Waiting for Review'

    client.get('/logout')

    # Reviewer can now approve cleanly
    login_as(client, 'reviewer@lumora.demo', 'Reviewer@123')
    res_approve = client.post(f'/content/{content_id}/decision', data={
        'outcome': 'Approve',
        'reason': 'All issues fixed. Approved for publishing.'
    }, follow_redirects=True)
    assert b"Decision recorded" in res_approve.data
    assert b"Approve" in res_approve.data

    with app.app_context():
        v2_final = db.session.get(Content, content_id).latest_version
        assert v2_final.status == 'Approved'


# SAFEGUARD 4: Reviewers cannot review their own uploads
def test_reviewer_cannot_review_own_upload(client, init_database, app):
    setup_test_rules(app)

    # Reviewer uploads their own content
    login_as(client, 'reviewer@lumora.demo', 'Reviewer@123')
    client.post('/content/new', data={
        'title': 'Reviewer Personal Post',
        'pasted_text': 'Lumora Plus ambient light for Rs. 2,499.'
    }, follow_redirects=True)

    with app.app_context():
        content = Content.query.filter_by(title='Reviewer Personal Post').first()
        content_id = content.id

    # Reviewer tries to approve their own content
    res_self = client.post(f'/content/{content_id}/decision', data={
        'outcome': 'Approve',
        'reason': 'Self approving'
    }, follow_redirects=True)

    assert b"Safeguard Violation: Reviewers cannot review or approve their own uploads." in res_self.data

    with app.app_context():
        c = db.session.get(Content, content_id)
        assert c.latest_version.decision is None
        audit = AuditLog.query.filter_by(action='SELF_REVIEW_BLOCKED').first()
        assert audit is not None


# SAFEGUARD 5: Creators cannot submit decisions (role protection)
def test_creator_cannot_review(client, init_database, app):
    content_id = create_sample_flyer(client, app)

    login_as(client, 'creator@lumora.demo', 'Creator@123')
    res_decide = client.post(f'/content/{content_id}/decision', data={
        'outcome': 'Approve',
        'reason': 'Creator trying to self-approve'
    })
    assert res_decide.status_code == 403
