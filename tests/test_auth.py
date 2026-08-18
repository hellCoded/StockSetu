import pytest
from flask import session

def test_login_page_renders(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Sign In" in response.data

def test_login_success(client):
    response = client.post('/login', data={
        'identifier': 'testadmin',
        'password': 'AdminPass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back, testadmin" in response.data

def test_login_invalid_password(client):
    response = client.post('/login', data={
        'identifier': 'testadmin',
        'password': 'WrongPassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid username/email or password" in response.data

def test_login_unregistered_user_redirects_to_register(client):
    response = client.post('/login', data={
        'identifier': 'nonexistentuser99',
        'password': 'SomePassword123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Account not found" in response.data

def test_registration_success(client):
    response = client.post('/register', data={
        'name': 'New User',
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful" in response.data

def test_registration_duplicate_username(client):
    response = client.post('/register', data={
        'name': 'Test Admin',
        'username': 'testadmin',
        'email': 'unique@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Username is already taken" in response.data

def test_logout(admin_client):
    response = admin_client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been logged out" in response.data

def test_update_profile_info(admin_client):
    response = admin_client.post('/profile', data={
        'action_type': 'update_profile',
        'name': 'Updated Admin Name',
        'email': 'updatedadmin@example.com'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Profile details updated successfully" in response.data
    assert b"Updated Admin Name" in response.data

def test_change_password_success(admin_client):
    response = admin_client.post('/profile', data={
        'action_type': 'change_password',
        'current_password': 'AdminPass123',
        'password': 'NewAdminPass123',
        'confirm_password': 'NewAdminPass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Password changed successfully" in response.data

def test_change_password_invalid_current(admin_client):
    response = admin_client.post('/profile', data={
        'action_type': 'change_password',
        'current_password': 'WrongCurrentPassword',
        'password': 'NewAdminPass123',
        'confirm_password': 'NewAdminPass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Current password is incorrect" in response.data

def test_logout_sets_user_inactive(admin_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({'username': 'testadmin'})
    assert user is not None
    # User was active before logout
    db.users.update_one({'_id': user['_id']}, {'$set': {'is_active': True}})
    
    response = admin_client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    
    updated = db.users.find_one({'_id': user['_id']})
    assert updated['is_active'] is False

def test_api_leave_marks_user_inactive(admin_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({'username': 'testadmin'})
    db.users.update_one({'_id': user['_id']}, {'$set': {'is_active': True}})

    response = admin_client.post('/api/auth/leave')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True

    updated = db.users.find_one({'_id': user['_id']})
    assert updated['is_active'] is False

def test_api_offline_marks_user_inactive(admin_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({'username': 'testadmin'})
    db.users.update_one({'_id': user['_id']}, {'$set': {'is_active': True}})

    response = admin_client.post('/api/auth/offline')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True

    updated = db.users.find_one({'_id': user['_id']})
    assert updated['is_active'] is False

def test_api_heartbeat_refreshes_active(admin_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({'username': 'testadmin'})
    
    response = admin_client.post('/api/auth/heartbeat')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    assert json_data['logged_in'] is True

    updated = db.users.find_one({'_id': user['_id']})
    assert updated['is_active'] is True
    assert 'last_active_at' in updated

def test_cleanup_stale_active_users(app, mock_mongo):
    from datetime import datetime, timezone, timedelta
    from inventory_app.services.auth_service import cleanup_stale_active_users
    db = mock_mongo['inventory_test_db']
    
    # Create a user with old last_active_at
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.users.insert_one({
        'username': 'staleuser',
        'is_active': True,
        'last_active_at': old_time
    })
    
    with app.app_context():
        cleanup_stale_active_users(stale_threshold_seconds=60)
    stale = db.users.find_one({'username': 'staleuser'})
    assert stale['is_active'] is False

