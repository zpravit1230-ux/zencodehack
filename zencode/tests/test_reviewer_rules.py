from app.models import db, User, Role, ReviewerRule, AuditLog, Content, ContentVersion

def login_as(client, email, password):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

def test_manager_profile_and_reviewer_rules_crud(client, init_database, app):
    # 1. Non-manager access is blocked with 403
    login_as(client, 'creator@lumora.demo', 'Creator@123')
    res = client.get('/admin/profile')
    assert res.status_code == 403

    res_add = client.post('/admin/reviewer-rules/add', data={
        'title': 'Unauthorized Rule',
        'category': 'DETAILS',
        'instructions': 'Should fail',
        'severity': 'Mandatory'
    })
    assert res_add.status_code == 403
    client.get('/logout')

    # 2. Manager accesses profile
    login_as(client, 'manager@lumora.demo', 'Manager@123')
    res_prof = client.get('/admin/profile')
    assert res_prof.status_code == 200
    assert b'Manager Profile &amp; Reviewer Directives' in res_prof.data
    assert b'How Rules Vary Across Reviewers' in res_prof.data

    with app.app_context():
        reviewer = User.query.filter_by(email='reviewer@lumora.demo').first()
        reviewer_id = reviewer.id

    # 3. Manager adds a rule for the Reviewer
    res_create = client.post('/admin/reviewer-rules/add', data={
        'reviewer_id': reviewer_id,
        'title': 'Strict Warranty Check',
        'category': 'DETAILS',
        'instructions': 'Ensure all copy explicitly confirms 2-year warranty.',
        'severity': 'Mandatory',
        'active': True
    }, follow_redirects=True)
    assert res_create.status_code == 200
    assert b'Strict Warranty Check' in res_create.data

    with app.app_context():
        rule = ReviewerRule.query.filter_by(title='Strict Warranty Check').first()
        assert rule is not None
        assert rule.reviewer_id == reviewer_id
        assert rule.category == 'DETAILS'
        assert rule.severity == 'Mandatory'
        assert rule.active is True
        rule_id = rule.id

        # Verify audit log recorded
        audit = AuditLog.query.filter_by(action='REVIEWER_RULE_ADDED').first()
        assert audit is not None
        assert 'Strict Warranty Check' in audit.details

    # 4. Manager edits the rule
    res_edit = client.post(f'/admin/reviewer-rules/{rule_id}/edit', data={
        'reviewer_id': reviewer_id,
        'title': 'Strict Warranty & Specs Check',
        'category': 'DETAILS',
        'instructions': 'Updated instructions for warranty and specs.',
        'severity': 'Recommended',
        'active': True
    }, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b'Strict Warranty &amp; Specs Check' in res_edit.data

    with app.app_context():
        updated_rule = db.session.get(ReviewerRule, rule_id)
        assert updated_rule.title == 'Strict Warranty & Specs Check'
        assert updated_rule.severity == 'Recommended'

    # 5. Manager toggles the rule
    client.post(f'/admin/reviewer-rules/{rule_id}/toggle', follow_redirects=True)
    with app.app_context():
        toggled_rule = db.session.get(ReviewerRule, rule_id)
        assert toggled_rule.active is False

    # 6. Delete rule
    client.post(f'/admin/reviewer-rules/{rule_id}/delete', follow_redirects=True)
    with app.app_context():
        deleted_rule = db.session.get(ReviewerRule, rule_id)
        assert deleted_rule is None


def test_rules_vary_per_reviewer_and_display_on_review(client, init_database, app):
    # Manager creates two different rules for two different reviewers
    login_as(client, 'manager@lumora.demo', 'Manager@123')

    with app.app_context():
        rev1 = User.query.filter_by(email='reviewer@lumora.demo').first()
        mgr = User.query.filter_by(email='manager@lumora.demo').first()

        # Add rule 1 for rev1
        r1 = ReviewerRule(
            reviewer_id=rev1.id,
            created_by_id=mgr.id,
            title='Price Scrutiny Checklist',
            category='DETAILS',
            instructions='Ensure price is Rs. 2,499.',
            severity='Mandatory',
            active=True
        )
        # Add rule 2 for mgr
        r2 = ReviewerRule(
            reviewer_id=mgr.id,
            created_by_id=mgr.id,
            title='Legal Promises Audit',
            category='PROMISES',
            instructions='Verify all promises match approved claims.',
            severity='Mandatory',
            active=True
        )
        db.session.add_all([r1, r2])
        db.session.commit()

    client.get('/logout')

    # Log in as reviewer1 -> sees their specific rule on dashboard
    login_as(client, 'reviewer@lumora.demo', 'Reviewer@123')
    res_dash = client.get('/dashboard/reviewer')
    assert res_dash.status_code == 200
    assert b'Price Scrutiny Checklist' in res_dash.data
    assert b'Legal Promises Audit' not in res_dash.data  # Rule 2 belongs to mgr, not rev1!

    # Create a piece of content to inspect detail view
    with app.app_context():
        creator = User.query.filter_by(email='creator@lumora.demo').first()
        content = Content(title='Test Product Post', creator_id=creator.id)
        db.session.add(content)
        db.session.commit()

        v = ContentVersion(
            content_id=content.id,
            version_number=1,
            raw_text='Test copy',
            extracted_text='Test copy',
            status='Waiting for Review'
        )
        db.session.add(v)
        db.session.commit()
        content_id = content.id

    res_detail = client.get(f'/content/{content_id}')
    assert res_detail.status_code == 200
    assert b'Price Scrutiny Checklist' in res_detail.data
    assert b'Your Assigned Review Directives (from Manager)' in res_detail.data

