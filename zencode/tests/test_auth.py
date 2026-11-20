from app.models import User, Role

def test_register_creator(client, app):
    response = client.post('/register', data={
        'full_name': 'Test Creator',
        'email': 'newuser@lumora.demo',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful" in response.data

    with app.app_context():
        user = User.query.filter_by(email='newuser@lumora.demo').first()
        assert user is not None
        assert user.role_name == 'Creator'
        assert user.check_password('Password@123')


def test_register_validation(client):
    # Short password
    r1 = client.post('/register', data={
        'full_name': 'Test Short',
        'email': 'short@lumora.demo',
        'password': 'short',
        'confirm_password': 'short'
    })
    assert b"Password must be at least 8 characters long." in r1.data

    # No number in password
    r2 = client.post('/register', data={
        'full_name': 'Test NoNum',
        'email': 'nonum@lumora.demo',
        'password': 'PasswordOnly',
        'confirm_password': 'PasswordOnly'
    })
    assert b"Password must contain at least one letter and one number." in r2.data


def test_login_and_logout(client, init_database):
    # Valid login
    res = client.post('/login', data={
        'email': 'creator@lumora.demo',
        'password': 'Creator@123'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Creator Workspace" in res.data
    assert b"Priya Writer" in res.data

    # Logout
    logout_res = client.get('/logout', follow_redirects=True)
    assert logout_res.status_code == 200
    assert b"You have been logged out securely." in logout_res.data


def test_login_lockout_after_five_failed_attempts(client, init_database, app):
    email = 'creator@lumora.demo'
    
    # 4 failed attempts
    for i in range(1, 5):
        r = client.post('/login', data={'email': email, 'password': 'WrongPassword!'}, follow_redirects=True)
        assert f"{5 - i} attempt(s) remaining" in r.data.decode('utf-8')

    # 5th failed attempt triggers lockout
    r5 = client.post('/login', data={'email': email, 'password': 'WrongPassword!'}, follow_redirects=True)
    assert b"locked for 15 minutes" in r5.data

    with app.app_context():
        u = User.query.filter_by(email=email).first()
        assert u.failed_logins >= 5
        assert u.is_locked is True

    # Attempting to login even with correct password is now blocked
    r_locked = client.post('/login', data={'email': email, 'password': 'Creator@123'}, follow_redirects=True)
    assert b"Account is temporarily locked" in r_locked.data

