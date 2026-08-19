import pytest
from flask import session

def test_login_page_renders(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Sign In" in response.data

def test_login_success(client):
    response = client.post('/login', data={
        'identifier': 'ADM-001',
        'password': 'AdminPass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back" in response.data

def test_login_invalid_password(client):
    response = client.post('/login', data={
        'identifier': 'ADM-001',
        'password': 'WrongPassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid" in response.data and b"password" in response.data

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
        'employee_id': 'EMP-9999',
        'email': 'newuser@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful" in response.data

def test_registration_duplicate_employee_id(client):
    response = client.post('/register', data={
        'name': 'Test Admin',
        'employee_id': 'ADM-001',
        'email': 'unique@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"already registered" in response.data

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

def test_deactivate_inactive_users_function(app, mock_mongo):
    from datetime import datetime, timezone, timedelta
    from inventory_app.services.auth_service import deactivate_inactive_users
    db = mock_mongo['inventory_test_db']
    
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)
    past_2h = datetime.now(timezone.utc) - timedelta(hours=2)
    
    db.users.insert_one({
        "username": "offlineuser",
        "email": "offline@test.com",
        "is_active": True,
        "last_active_at": past_13h
    })
    db.users.insert_one({
        "username": "activeuser",
        "email": "active@test.com",
        "is_active": True,
        "last_active_at": past_2h
    })
    
    with app.app_context():
        deactivated_count = deactivate_inactive_users(inactivity_hours=12.0)
        assert deactivated_count >= 1
        
        offline_u = db.users.find_one({"username": "offlineuser"})
        active_u = db.users.find_one({"username": "activeuser"})
        assert offline_u["is_active"] is False
        assert active_u["is_active"] is True

def test_session_auto_logout_after_12_hours_inactivity(admin_client, mock_mongo):
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"username": "testadmin"})
    
    # Simulate session with activity from 13 hours ago
    past_13h_ts = (datetime.now(timezone.utc) - timedelta(hours=13)).timestamp()
    with admin_client.session_transaction() as sess:
        sess['last_active_at'] = past_13h_ts
        
    response = admin_client.get('/', follow_redirects=True)
    assert response.status_code == 200
    # Should redirect to login and show inactivity message
    assert b"12 hours of inactivity" in response.data or b"Sign In" in response.data
    
    # User doc in DB should now be deactivated
    updated_user = db.users.find_one({"_id": ObjectId(user["_id"])})
    assert updated_user["is_active"] is False

def test_deactivated_user_session_redirected_to_login(admin_client, mock_mongo):
    from bson import ObjectId
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"username": "testadmin"})
    
    # Deactivate user in DB
    db.users.update_one({"_id": ObjectId(user["_id"])}, {"$set": {"is_active": False}})
    
    response = admin_client.get('/', follow_redirects=True)
    assert response.status_code == 200
    assert b"deactivated" in response.data.lower() or b"Sign In" in response.data
