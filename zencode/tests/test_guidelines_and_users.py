from app.models import db, Guideline, User, Role, AuditLog

def login_as(client, email, password):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

def test_manager_can_add_guideline_and_creator_cannot(client, init_database, app):
    # Creator tries to access guidelines -> 403
    login_as(client, 'creator@lumora.demo', 'Creator@123')
    res = client.get('/guidelines/')
    assert res.status_code == 403

    post_res = client.post('/guidelines/add', data={
        'type': 'WORDS',
        'key': 'Banned Term X',
        'value': 'Preferred Term Y',
        'active': True
    })
    assert post_res.status_code == 403

    client.get('/logout')

    # Manager adds guideline -> 200/redirect and persists
    login_as(client, 'manager@lumora.demo', 'Manager@123')
    res_mgr_page = client.get('/guidelines/')
    assert res_mgr_page.status_code == 200

    res_add = client.post('/guidelines/add', data={
        'type': 'WORDS',
        'key': 'Lumora Pro',
        'value': 'Lumora Plus',
        'description': 'Prototype naming rule',
        'active': True
    }, follow_redirects=True)
    assert res_add.status_code == 200

    with app.app_context():
        g = Guideline.query.filter_by(key='Lumora Pro').first()
        assert g is not None
        assert g.value == 'Lumora Plus'
        assert g.type == 'WORDS'
        assert g.active is True

        # Check audit log recorded
        audit = AuditLog.query.filter_by(action='GUIDELINE_ADD').first()
        assert audit is not None
        assert 'Lumora Pro' in audit.details


def test_manager_can_change_role_and_creator_cannot(client, init_database, app):
    # Creator tries to access Users page -> 403
    login_as(client, 'creator@lumora.demo', 'Creator@123')
    res_users = client.get('/admin/users')
    assert res_users.status_code == 403

    # Creator tries to promote themselves to Manager -> 403
    with app.app_context():
        creator_user = User.query.filter_by(email='creator@lumora.demo').first()
        creator_id = creator_user.id

    res_hack = client.post(f'/admin/users/{creator_id}/role', data={'role_name': 'Manager'})
    assert res_hack.status_code == 403

    client.get('/logout')

    # Manager changes creator role to Reviewer
    login_as(client, 'manager@lumora.demo', 'Manager@123')
    res_promote = client.post(f'/admin/users/{creator_id}/role', data={'role_name': 'Reviewer'}, follow_redirects=True)
    assert res_promote.status_code == 200

    with app.app_context():
        updated_user = db.session.get(User, creator_id)
        assert updated_user.role_name == 'Reviewer'

        # Check audit log recorded
        audit = AuditLog.query.filter_by(action='ROLE_CHANGE').first()
        assert audit is not None
        assert 'Reviewer' in audit.details
