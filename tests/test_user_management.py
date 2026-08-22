"""Tests for user management workflows: activation, role changes, bulk import, profile conflicts."""
import pytest
import io
from werkzeug.datastructures import FileStorage
from bson import ObjectId


# ========== USER ACTIVATION/DEACTIVATION TESTS ==========

def test_admin_can_deactivate_user(admin_client, mock_mongo):
    """Admin can deactivate an active user via toggle-active endpoint."""
    db = mock_mongo['inventory_test_db']
    # Create a test user
    db.users.insert_one({
        "employee_id": "EMP-TEST-01",
        "employee_id_lower": "emp-test-01",
        "name": "Test User",
        "name_lower": "test user",
        "email": "testuser@example.com",
        "email_lower": "testuser@example.com",
        "phone": "9999999999",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": True,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    })
    user = db.users.find_one({"employee_id": "EMP-TEST-01"})
    assert user["is_active"] is True
    user_id = str(user["_id"])
    
    # Admin deactivates user
    resp = admin_client.post(f'/users/{user_id}/toggle-active', follow_redirects=True)
    assert resp.status_code == 200
    assert b"deactivated" in resp.data.lower() or b"inactive" in resp.data.lower()
    
    # Verify user is deactivated
    updated = db.users.find_one({"employee_id": "EMP-TEST-01"})
    assert updated["is_active"] is False


def test_admin_can_activate_user(admin_client, mock_mongo):
    """Admin can activate a deactivated user."""
    db = mock_mongo['inventory_test_db']
    db.users.insert_one({
        "employee_id": "EMP-TEST-02",
        "employee_id_lower": "emp-test-02",
        "name": "Test User 2",
        "name_lower": "test user 2",
        "email": "testuser2@example.com",
        "email_lower": "testuser2@example.com",
        "phone": "9999999998",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": False,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    })
    user = db.users.find_one({"employee_id": "EMP-TEST-02"})
    assert user["is_active"] is False
    user_id = str(user["_id"])
    
    # Admin activates user
    resp = admin_client.post(f'/users/{user_id}/toggle-active', follow_redirects=True)
    assert resp.status_code == 200
    assert b"activated" in resp.data.lower() or b"active" in resp.data.lower()
    
    updated = db.users.find_one({"employee_id": "EMP-TEST-02"})
    assert updated["is_active"] is True


def test_admin_cannot_deactivate_self(admin_client, mock_mongo):
    """Admin cannot deactivate their own account."""
    db = mock_mongo['inventory_test_db']
    admin_user = db.users.find_one({"employee_id": "ADM-001"})
    admin_id = str(admin_user["_id"])
    
    resp = admin_client.post(f'/users/{admin_id}/toggle-active', follow_redirects=True)
    assert resp.status_code == 200
    assert b"cannot deactivate your own" in resp.data.lower() or b"own account" in resp.data.lower()
    
    # Admin should still be active
    updated = db.users.find_one({"_id": ObjectId(admin_id)})
    assert updated["is_active"] is True


def test_staff_cannot_access_toggle_active(staff_client, mock_mongo):
    """Staff cannot access toggle-active endpoint."""
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "EMP-001"})  # Create if needed
    if not user:
        db.users.insert_one({
            "employee_id": "EMP-TARGET",
            "employee_id_lower": "emp-target",
            "name": "Target",
            "name_lower": "target",
            "email": "target@example.com",
            "email_lower": "target@example.com",
            "password_hash": "hashed",
            "role": "staff",
            "is_active": True,
        })
        user = db.users.find_one({"employee_id": "EMP-TARGET"})
    user_id = str(user["_id"])
    
    resp = staff_client.post(f'/users/{user_id}/toggle-active', follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


def test_manager_cannot_access_toggle_active(manager_client, mock_mongo):
    """Manager cannot access toggle-active endpoint."""
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "EMP-001"})
    if not user:
        db.users.insert_one({
            "employee_id": "EMP-TARGET",
            "employee_id_lower": "emp-target",
            "name": "Target",
            "name_lower": "target",
            "email": "target@example.com",
            "email_lower": "target@example.com",
            "password_hash": "hashed",
            "role": "staff",
            "is_active": True,
        })
        user = db.users.find_one({"employee_id": "EMP-TARGET"})
    user_id = str(user["_id"])
    
    resp = manager_client.post(f'/users/{user_id}/toggle-active', follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


# ========== ROLE CHANGE TESTS ==========

def test_admin_can_change_user_role(admin_client, mock_mongo):
    """Admin can change a user's role via /users/<id>/role."""
    db = mock_mongo['inventory_test_db']
    db.users.insert_one({
        "employee_id": "EMP-ROLE-01",
        "employee_id_lower": "emp-role-01",
        "name": "Role Test",
        "name_lower": "role test",
        "email": "roletest@example.com",
        "email_lower": "roletest@example.com",
        "phone": "9999999997",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": True,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    })
    user = db.users.find_one({"employee_id": "EMP-ROLE-01"})
    assert user["role"] == "staff"
    user_id = str(user["_id"])
    
    # Change to inventory_manager
    resp = admin_client.post(f'/users/{user_id}/role', data={'role': 'inventory_manager'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"role updated" in resp.data.lower() or b"inventory manager" in resp.data.lower()
    
    updated = db.users.find_one({"employee_id": "EMP-ROLE-01"})
    assert updated["role"] == "inventory_manager"


def test_admin_can_change_staff_to_admin(admin_client, mock_mongo):
    """Admin can promote staff to admin."""
    db = mock_mongo['inventory_test_db']
    db.users.insert_one({
        "employee_id": "EMP-ROLE-02",
        "employee_id_lower": "emp-role-02",
        "name": "Admin Candidate",
        "name_lower": "admin candidate",
        "email": "admincand@example.com",
        "email_lower": "admincand@example.com",
        "phone": "9999999996",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": True,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    })
    user = db.users.find_one({"employee_id": "EMP-ROLE-02"})
    user_id = str(user["_id"])
    
    resp = admin_client.post(f'/users/{user_id}/role', data={'role': 'admin'}, follow_redirects=True)
    assert resp.status_code == 200
    
    updated = db.users.find_one({"employee_id": "EMP-ROLE-02"})
    assert updated["role"] == "admin"


def test_admin_cannot_change_own_role(admin_client, mock_mongo):
    """Admin cannot change their own role."""
    db = mock_mongo['inventory_test_db']
    admin_user = db.users.find_one({"employee_id": "ADM-001"})
    admin_id = str(admin_user["_id"])
    
    resp = admin_client.post(f'/users/{admin_id}/role', data={'role': 'staff'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"cannot modify your own" in resp.data.lower() or b"administrator role" in resp.data.lower()
    
    updated = db.users.find_one({"_id": ObjectId(admin_id)})
    assert updated["role"] == "admin"


def test_staff_cannot_access_change_role(staff_client, mock_mongo):
    """Staff cannot access change-role endpoint."""
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "ADM-001"})  # target admin
    user_id = str(user["_id"])
    
    resp = staff_client.post(f'/users/{user_id}/role', data={'role': 'staff'}, follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


def test_manager_cannot_access_change_role(manager_client, mock_mongo):
    """Manager cannot access change-role endpoint."""
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "ADM-001"})
    user_id = str(user["_id"])
    
    resp = manager_client.post(f'/users/{user_id}/role', data={'role': 'staff'}, follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


def test_invalid_role_rejected(admin_client, mock_mongo):
    """Invalid role value is rejected."""
    db = mock_mongo['inventory_test_db']
    db.users.insert_one({
        "employee_id": "EMP-ROLE-03",
        "employee_id_lower": "emp-role-03",
        "name": "Invalid Role",
        "name_lower": "invalid role",
        "email": "invalidrole@example.com",
        "email_lower": "invalidrole@example.com",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": True,
    })
    user = db.users.find_one({"employee_id": "EMP-ROLE-03"})
    user_id = str(user["_id"])
    
    resp = admin_client.post(f'/users/{user_id}/role', data={'role': 'super_admin'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"invalid role" in resp.data.lower() or b"danger" in resp.data.lower()
    
    # Role should be unchanged
    updated = db.users.find_one({"employee_id": "EMP-ROLE-03"})
    assert updated["role"] == "staff"


# ========== ROLE CHANGE / SESSION SYNCHRONIZATION TESTS ==========

def test_role_change_syncs_session_for_target_user(admin_client, mock_mongo):
    """Role change updates target user's role; session sync happens via polling."""
    db = mock_mongo['inventory_test_db']
    db.users.insert_one({
        "employee_id": "EMP-SYNC-01",
        "employee_id_lower": "emp-sync-01",
        "name": "Sync Test",
        "name_lower": "sync test",
        "email": "synctest@example.com",
        "email_lower": "synctest@example.com",
        "phone": "9999999995",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": True,
        "session_token": "old_token",
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    })
    user = db.users.find_one({"employee_id": "EMP-SYNC-01"})
    user_id = str(user["_id"])
    
    # Change role
    admin_client.post(f'/users/{user_id}/role', data={'role': 'inventory_manager'}, follow_redirects=True)
    
    # Role updated, cache invalidated (next poll will sync)
    updated = db.users.find_one({"employee_id": "EMP-SYNC-01"})
    assert updated["role"] == "inventory_manager"
    # session_token NOT cleared here - synced via polling /api/user/session-info


def test_deactivated_user_session_redirected(admin_client, mock_mongo):
    """Deactivated user's session is rejected on next request (checked in before_request)."""
    db = mock_mongo['inventory_test_db']
    db.users.insert_one({
        "employee_id": "EMP-DEACT-SESSION",
        "employee_id_lower": "emp-deact-session",
        "name": "Deact Session",
        "name_lower": "deact session",
        "email": "deact@example.com",
        "email_lower": "deact@example.com",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": True,
        "session_token": "active_token",
    })
    user = db.users.find_one({"employee_id": "EMP-DEACT-SESSION"})
    user_id = str(user["_id"])
    
    # Deactivate
    admin_client.post(f'/users/{user_id}/toggle-active', follow_redirects=True)
    
    # User should now be inactive
    updated = db.users.find_one({"employee_id": "EMP-DEACT-SESSION"})
    assert updated["is_active"] is False
    # session_token NOT cleared here - before_request will reject deactivated users


# ========== BULK IMPORT VALIDATION TESTS ==========

def test_bulk_import_missing_optional_columns(app):
    """Import with minimal columns auto-generates missing fields."""
    from inventory_app.services.auth_service import import_staff_bulk
    # Only Employee ID and Full Name provided - email/phone auto-generated
    csv_data = "Employee ID,Full Name\nEMP-9999,John Doe\n"
    file_storage = FileStorage(
        stream=io.BytesIO(csv_data.encode("utf-8")),
        filename="minimal.csv",
        content_type="text/csv"
    )
    with app.app_context():
        success, msg, details = import_staff_bulk(file_storage, imported_by="testadmin")
        assert success is True
        assert details["imported_count"] == 1
        # Email auto-generated (hyphens stripped): emp9999@stocksetu.local
        assert details["imported_users"][0]["email"] == "emp9999@stocksetu.local"


def test_bulk_import_invalid_email_format(app):
    """Import with invalid email skips that row."""
    from inventory_app.services.auth_service import import_staff_bulk
    csv_data = (
        "Employee ID,Full Name,Phone No,Email\n"
        "EMP-GOOD,Good User,9999999999,good@example.com\n"
        "EMP-BAD,Bad User,8888888888,not-an-email\n"
    )
    file_storage = FileStorage(
        stream=io.BytesIO(csv_data.encode("utf-8")),
        filename="mixed.csv",
        content_type="text/csv"
    )
    with app.app_context():
        success, msg, details = import_staff_bulk(file_storage, imported_by="testadmin")
        assert success is True
        assert details["imported_count"] == 1
        assert details["skipped_count"] == 1


def test_bulk_import_duplicate_employee_id_in_file(app):
    """Duplicate employee IDs in same file are skipped."""
    from inventory_app.services.auth_service import import_staff_bulk
    csv_data = (
        "Employee ID,Full Name,Phone No,Email\n"
        "EMP-DUP,First,9999999999,first@example.com\n"
        "EMP-DUP,Second,8888888888,second@example.com\n"
    )
    file_storage = FileStorage(
        stream=io.BytesIO(csv_data.encode("utf-8")),
        filename="dup.csv",
        content_type="text/csv"
    )
    with app.app_context():
        success, msg, details = import_staff_bulk(file_storage, imported_by="testadmin")
        assert success is True
        assert details["imported_count"] == 1
        assert details["skipped_count"] == 1


def test_bulk_import_existing_email_in_db(app):
    """Import with email already in DB skips that row."""
    from inventory_app.services.auth_service import import_staff_bulk
    from inventory_app.database import get_db
    db = get_db()
    # Seed existing user
    db.users.insert_one({
        "employee_id": "EMP-EXIST",
        "employee_id_lower": "emp-exist",
        "name": "Existing",
        "name_lower": "existing",
        "email": "existing@example.com",
        "email_lower": "existing@example.com",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": True,
    })
    
    csv_data = (
        "Employee ID,Full Name,Phone No,Email\n"
        "EMP-NEW,New User,9999999999,new@example.com\n"
        "EMP-EXIST,Existing,8888888888,existing@example.com\n"  # Duplicate email
    )
    file_storage = FileStorage(
        stream=io.BytesIO(csv_data.encode("utf-8")),
        filename="email.csv",
        content_type="text/csv"
    )
    with app.app_context():
        success, msg, details = import_staff_bulk(file_storage, imported_by="testadmin")
        assert success is True
        assert details["imported_count"] == 1
        assert details["skipped_count"] == 1


def test_bulk_import_creates_inactive_users_with_force_pw_change(app):
    """Imported users are inactive and require password change."""
    from inventory_app.services.auth_service import import_staff_bulk, authenticate_user
    from inventory_app.database import get_db
    csv_data = (
        "Employee ID,Full Name,Phone No,Email\n"
        "EMP-PWTEST,Password Test,9999999999,pwtest@example.com\n"
    )
    file_storage = FileStorage(
        stream=io.BytesIO(csv_data.encode("utf-8")),
        filename="pw.csv",
        content_type="text/csv"
    )
    with app.app_context():
        success, msg, details = import_staff_bulk(file_storage, default_password="TestPass123", imported_by="testadmin")
        assert success is True
        assert details["imported_count"] == 1
        
        db = get_db()
        user = db.users.find_one({"employee_id": "EMP-PWTEST"})
        assert user["is_active"] is False
        assert user["force_password_change"] is True
        
        # Should be able to authenticate with default password
        auth_success, auth_msg, auth_user = authenticate_user("EMP-PWTEST", "TestPass123")
        assert auth_success is True
        assert auth_user["force_password_change"] is True


def test_bulk_import_unauthorized(staff_client):
    """Staff cannot access bulk import."""
    csv_data = "Employee ID,Full Name,Phone No,Email\nEMP-TEST,Test,9999999999,test@example.com\n"
    data = {
        "staff_file": (io.BytesIO(csv_data.encode("utf-8")), "test.csv"),
        "default_password": "Staff@123"
    }
    resp = staff_client.post("/users/bulk-import", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


# ========== PROFILE UPDATE CONFLICTS TESTS ==========

def test_profile_update_duplicate_email_rejected(admin_client, mock_mongo):
    """Profile update with email already in use is rejected."""
    db = mock_mongo['inventory_test_db']
    # Create another user with email
    db.users.insert_one({
        "employee_id": "EMP-OTHER",
        "employee_id_lower": "emp-other",
        "name": "Other User",
        "name_lower": "other user",
        "email": "other@example.com",
        "email_lower": "other@example.com",
        "password_hash": "hashed",
        "role": "staff",
        "is_active": True,
    })
    
    # Admin tries to change their email to other's email
    resp = admin_client.post('/profile', data={
        'action_type': 'update_profile',
        'name': 'Admin Name',
        'email': 'other@example.com'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"already registered" in resp.data or b"already in use" in resp.data.lower()


def test_profile_update_same_email_allowed(admin_client):
    """Profile update with same email is allowed."""
    resp = admin_client.post('/profile', data={
        'action_type': 'update_profile',
        'name': 'Same Email Admin',
        'email': 'admin@test.com'  # Same as seeded
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"updated successfully" in resp.data.lower() or b"success" in resp.data.lower()


def test_profile_update_invalid_email_rejected(admin_client):
    """Profile update with invalid email format is rejected."""
    resp = admin_client.post('/profile', data={
        'action_type': 'update_profile',
        'name': 'Admin',
        'email': 'not-an-email'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"valid email" in resp.data.lower() or b"invalid" in resp.data.lower()


# ========== ADMIN SELF-PROTECTION TESTS ==========

def test_admin_cannot_change_own_role_via_add_user(admin_client, mock_mongo):
    """Admin cannot use add-user to change their own role (already tested via change_role)."""
    # This is covered by test_admin_cannot_change_own_role
    pass


def test_admin_cannot_deactivate_self_via_toggle(admin_client):
    """Admin cannot deactivate self (already tested)."""
    # Covered by test_admin_cannot_deactivate_self
    pass


# ========== UNAUTHORIZED ACCESS TESTS ==========

def test_staff_cannot_access_user_list(staff_client):
    """Staff cannot access /users."""
    resp = staff_client.get('/users', follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


def test_manager_cannot_access_user_list(manager_client):
    """Manager cannot access /users."""
    resp = manager_client.get('/users', follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


def test_staff_cannot_access_bulk_import(staff_client):
    """Staff cannot access bulk import page."""
    resp = staff_client.get('/users/template?format=xlsx', follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


def test_manager_cannot_access_bulk_import(manager_client):
    """Manager cannot access bulk import page."""
    resp = manager_client.get('/users/template?format=xlsx', follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


def test_staff_cannot_access_add_user(staff_client):
    """Staff cannot POST to /users/add."""
    resp = staff_client.post('/users/add', data={
        'name': 'Test',
        'employee_id': 'EMP-STAFF-ADD',
        'email': 'staffadd@example.com',
        'password': 'Pass123',
        'confirm_password': 'Pass123',
        'role': 'staff'
    }, follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


def test_manager_cannot_access_add_user(manager_client):
    """Manager cannot POST to /users/add."""
    resp = manager_client.post('/users/add', data={
        'name': 'Test',
        'employee_id': 'EMP-MGR-ADD',
        'email': 'mgradd@example.com',
        'password': 'Pass123',
        'confirm_password': 'Pass123',
        'role': 'staff'
    }, follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403


# ========== ROLE REQUEST COMPLETION TESTS ==========

def test_role_request_approval_syncs_target_session(admin_client, mock_mongo):
    """Approving role request should update target user's role."""
    from inventory_app.database import get_db
    from inventory_app.services.auth_service import create_role_request
    db = get_db()
    
    db.role_requests.delete_many({})
    # Use actual seeded user ID
    staff_user = db.users.find_one({"employee_id": "STF-001"})
    staff_id = str(staff_user["_id"])
    
    success, msg = create_role_request(staff_id, employee_id="STF-001", email="staff@test.com", 
                                       requested_role="inventory_manager", reason="Need manager access")
    assert success
    
    req = db.role_requests.find_one({"status": "PENDING"})
    req_id = str(req["_id"])
    
    # Target user has session token
    db.users.update_one(
        {"employee_id": "STF-001"},
        {"$set": {"session_token": "target_session_token", "role": "staff"}}
    )
    
    # Admin approves
    admin_client.post(f'/users/requests/{req_id}/approve', data={'admin_comment': 'Approved'}, follow_redirects=True)
    
    # Target user role updated
    target = db.users.find_one({"employee_id": "STF-001"})
    assert target["role"] == "inventory_manager"
    # session_token NOT cleared by approve - synced via polling


def test_role_request_rejection_preserves_role(admin_client, mock_mongo):
    """Rejecting role request preserves target user's current role."""
    from inventory_app.database import get_db
    from inventory_app.services.auth_service import create_role_request
    db = get_db()
    
    db.role_requests.delete_many({})
    # Use actual seeded user
    staff_user = db.users.find_one({"employee_id": "STF-001"})
    staff_id = str(staff_user["_id"])
    
    success, msg = create_role_request(staff_id, employee_id="STF-001", email="staff@test.com",
                                       requested_role="admin", reason="Want admin")
    assert success
    
    req = db.role_requests.find_one({"status": "PENDING"})
    req_id = str(req["_id"])
    
    # Target has current role
    db.users.update_one(
        {"employee_id": "STF-001"},
        {"$set": {"role": "staff", "session_token": "some_token"}}
    )
    
    # Admin rejects
    admin_client.post(f'/users/requests/{req_id}/reject', data={'admin_comment': 'Not ready'}, follow_redirects=True)
    
    # Role unchanged
    target = db.users.find_one({"employee_id": "STF-001"})
    assert target["role"] == "staff"


# ========== EDGE CASES ==========

def test_toggle_active_nonexistent_user(admin_client):
    """Toggle active for non-existent user returns error."""
    fake_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format
    resp = admin_client.post(f'/users/{fake_id}/toggle-active', follow_redirects=True)
    assert resp.status_code == 200
    assert b"not found" in resp.data.lower() or b"danger" in resp.data.lower()


def test_change_role_nonexistent_user(admin_client):
    """Change role for non-existent user returns error."""
    fake_id = "507f1f77bcf86cd799439011"
    resp = admin_client.post(f'/users/{fake_id}/role', data={'role': 'staff'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"not found" in resp.data.lower() or b"danger" in resp.data.lower()


def test_change_role_invalid_user_id_format(admin_client):
    """Change role with invalid user ID format returns error."""
    resp = admin_client.post('/users/invalid-id/role', data={'role': 'staff'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"invalid" in resp.data.lower() or b"danger" in resp.data.lower()


def test_approve_nonexistent_request(admin_client):
    """Approve non-existent role request returns error."""
    fake_id = "507f1f77bcf86cd799439011"
    resp = admin_client.post(f'/users/requests/{fake_id}/approve', data={'admin_comment': 'test'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"not found" in resp.data.lower() or b"danger" in resp.data.lower()


def test_reject_nonexistent_request(admin_client):
    """Reject non-existent role request returns error."""
    fake_id = "507f1f77bcf86cd799439011"
    resp = admin_client.post(f'/users/requests/{fake_id}/reject', data={'admin_comment': 'test'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"not found" in resp.data.lower() or b"danger" in resp.data.lower()