def login_as(client, email, password):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

def test_role_access_dashboard_isolation(client, init_database):
    # Log in as Creator
    login_as(client, 'creator@lumora.demo', 'Creator@123')
    
    # Creator accesses Creator dashboard -> 200
    res_creator = client.get('/dashboard/creator')
    assert res_creator.status_code == 200

    # Creator tries to access Reviewer dashboard -> 403 Forbidden
    res_rev = client.get('/dashboard/reviewer')
    assert res_rev.status_code == 403

    # Creator tries to access Manager dashboard -> 403 Forbidden
    res_mgr = client.get('/dashboard/manager')
    assert res_mgr.status_code == 403

    # Logout
    client.get('/logout')

    # Log in as Reviewer
    login_as(client, 'reviewer@lumora.demo', 'Reviewer@123')
    res_rev_ok = client.get('/dashboard/reviewer')
    assert res_rev_ok.status_code == 200

    res_rev_to_mgr = client.get('/dashboard/manager')
    assert res_rev_to_mgr.status_code == 403

    # Logout
    client.get('/logout')

    # Log in as Manager
    login_as(client, 'manager@lumora.demo', 'Manager@123')
    res_mgr_ok = client.get('/dashboard/manager')
    assert res_mgr_ok.status_code == 200

