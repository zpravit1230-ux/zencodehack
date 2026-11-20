from app.models import Role, User, Guideline, Content, Issue

def test_app_starts_and_home_loads(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"BrandGuard" in response.data
    assert b"Lumora" in response.data

def test_roles_and_tables_exist(app):
    with app.app_context():
        roles = Role.query.all()
        role_names = [r.name for r in roles]
        assert 'Creator' in role_names
        assert 'Reviewer' in role_names
        assert 'Manager' in role_names

