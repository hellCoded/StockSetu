"""Tests for /api/user/session-info."""
import json
import pytest


def test_api_user_session_info_requires_auth(client):
    """Unauthenticated request should be rejected."""
    response = client.get('/api/user/session-info')
    assert response.status_code == 302


def test_api_user_session_info_returns_role(admin_client):
    """Returns current user's role, name, employee_id."""
    response = admin_client.get('/api/user/session-info')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'role' in data
    assert 'name' in data
    assert 'employee_id' in data
    assert data['role'] == 'admin'
    assert data['employee_id'] == 'ADM-001'
    assert data['name'] == 'Test Admin'


def test_api_user_session_info_staff(staff_client):
    """Works for staff role."""
    response = staff_client.get('/api/user/session-info')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['role'] == 'staff'
    assert data['employee_id'] == 'STF-001'
    assert data['name'] == 'Test Staff'


def test_api_user_session_info_manager(manager_client):
    """Works for manager role."""
    response = manager_client.get('/api/user/session-info')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['role'] == 'inventory_manager'
    assert data['employee_id'] == 'MGR-001'
    assert data['name'] == 'Test Manager'


def test_api_user_session_info_syncs_db_role(admin_client, mock_mongo):
    """Role is synced from DB if session is stale."""
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "ADM-001"})
    
    # Change role in DB directly (simulating admin role change)
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"role": "inventory_manager"}}
    )
    
    # Call session-info - should sync new role
    response = admin_client.get('/api/user/session-info')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['role'] == 'inventory_manager'  # Synced from DB
    
    # Verify session was updated
    with admin_client.session_transaction() as sess:
        assert sess['role'] == 'inventory_manager'


def test_api_user_session_info_inactive_user_returns_401(admin_client, mock_mongo):
    """Inactive user gets 401 and session cleared."""
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "ADM-001"})
    
    # Deactivate user
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_active": False}}
    )
    
    response = admin_client.get('/api/user/session-info')
    assert response.status_code == 401
    data = json.loads(response.data)
    assert data['error'] == 'session_expired'
    
    # Session should be cleared - subsequent requests fail
    response = admin_client.get('/api/user/session-info')
    assert response.status_code == 302  # Redirect to login


def test_api_user_session_info_single_session_enforcement(admin_client, mock_mongo):
    """If logged in elsewhere, returns 401 with reason."""
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "ADM-001"})
    
    # Simulate another login by changing session_token in DB
    new_token = "new_session_token_from_another_device"
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"session_token": new_token}}
    )
    
    # Current session has old token (or no token)
    with admin_client.session_transaction() as sess:
        sess['session_token'] = 'old_token'
    
    response = admin_client.get('/api/user/session-info')
    assert response.status_code == 401
    data = json.loads(response.data)
    assert data['error'] == 'session_expired'
    assert data['reason'] == 'logged_in_elsewhere'
    
    # Session should be cleared
    response = admin_client.get('/api/user/session-info')
    assert response.status_code == 302


def test_api_user_session_info_no_token_in_session(admin_client):
    """Works when session has no token (first login)."""
    # Remove session_token if present
    with admin_client.session_transaction() as sess:
        sess.pop('session_token', None)
    
    response = admin_client.get('/api/user/session-info')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['role'] == 'admin'


def test_api_user_session_info_missing_user_returns_401(admin_client, mock_mongo):
    """User deleted from DB returns 401."""
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "ADM-001"})
    
    # Delete user
    db.users.delete_one({"_id": user["_id"]})
    
    response = admin_client.get('/api/user/session-info')
    assert response.status_code == 401
    data = json.loads(response.data)
    assert data['error'] == 'session_expired'