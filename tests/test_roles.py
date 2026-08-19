import pytest

def test_staff_restricted_routes(staff_client):
    # Staff cannot access User Management
    res_users = staff_client.get('/users', follow_redirects=True)
    assert b"Forbidden" in res_users.data
    
    # Staff cannot access Product Add
    res_add = staff_client.get('/products/add', follow_redirects=True)
    assert b"Forbidden" in res_add.data

def test_manager_allowed_and_restricted_routes(manager_client):
    # Manager can access Product Add
    res_add = manager_client.get('/products/add')
    assert res_add.status_code == 200
    
    # Manager cannot access User Management
    res_users = manager_client.get('/users', follow_redirects=True)
    assert b"Forbidden" in res_users.data

def test_admin_full_access(admin_client):
    # Admin can access User Management
    res_users = admin_client.get('/users')
    assert res_users.status_code == 200
    
    # Admin can access Product Add
    res_add = admin_client.get('/products/add')
    assert res_add.status_code == 200

def test_admin_add_user_shows_modal_credentials(admin_client):
    res = admin_client.post('/users/add', data={
        'name': 'Created Staff',
        'employee_id': 'EMP-7777',
        'email': 'createdstaff@example.com',
        'password': 'Password123',
        'confirm_password': 'Password123',
        'role': 'staff'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"EMP-7777" in res.data
    assert b"user-credentials-modal" in res.data
    assert b"password you entered" in res.data

def test_staff_role_promotion_request_flow(staff_client, admin_client):
    # 1. Staff requests promotion to Manager
    res = staff_client.post('/request-promotion', data={'reason': 'Shift supervisor assignment'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"submitted to Administrator" in res.data
    
    # 2. Admin views user management and sees the pending request
    res_admin = admin_client.get('/users')
    assert res_admin.status_code == 200
    assert b"Shift supervisor assignment" in res_admin.data
    
    # 3. Get request ID from db
    from inventory_app.database import get_db
    db = get_db()
    req = db.role_requests.find_one({"status": "PENDING"})
    assert req is not None
    req_id = str(req["_id"])
    
    # 4. Admin approves request
    res_approve = admin_client.post(f'/users/requests/{req_id}/approve', follow_redirects=True)
    assert res_approve.status_code == 200
    assert b"now an Inventory Manager" in res_approve.data

def test_manager_role_elevation_to_admin_flow(manager_client, admin_client):
    # 1. Manager requests promotion to Admin
    res = manager_client.post('/request-promotion', data={
        'requested_role': 'admin',
        'reason': 'System co-administrator duties'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"submitted to Administrator for verification" in res.data
    
    # 2. Admin views user management and sees the pending request
    res_admin = admin_client.get('/users')
    assert res_admin.status_code == 200
    assert b"System co-administrator duties" in res_admin.data
    
    # 3. Get request ID from db
    from inventory_app.database import get_db
    db = get_db()
    req = db.role_requests.find_one({"reason": "System co-administrator duties", "status": "PENDING"})
    assert req is not None
    req_id = str(req["_id"])
    
    # 4. Admin approves request
    res_approve = admin_client.post(f'/users/requests/{req_id}/approve', follow_redirects=True)
    assert res_approve.status_code == 200
    assert b"now an Admin" in res_approve.data

def test_role_request_rejection_flow(staff_client, admin_client):
    # 1. Staff requests promotion
    res = staff_client.post('/request-promotion', data={'reason': 'Premature promotion request'}, follow_redirects=True)
    assert res.status_code == 200
    
    # 2. Get request ID from db
    from inventory_app.database import get_db
    db = get_db()
    req = db.role_requests.find_one({"reason": "Premature promotion request", "status": "PENDING"})
    assert req is not None
    req_id = str(req["_id"])
    
    # 3. Admin rejects request with a comment
    res_reject = admin_client.post(f'/users/requests/{req_id}/reject', data={'admin_comment': 'Please gain more experience first.'}, follow_redirects=True)
    assert res_reject.status_code == 200
    assert b"has been rejected" in res_reject.data
    
    # Verify the comment is persisted
    req_updated = db.role_requests.find_one({"_id": req["_id"]})
    assert req_updated["status"] == "REJECTED"
    assert req_updated["admin_comment"] == "Please gain more experience first."

def test_role_request_validation_and_duplicates(staff_client):
    from inventory_app.database import get_db
    db = get_db()
    db.role_requests.delete_many({}) # clear requests

    # 1. Request with empty reason should fail
    res_empty = staff_client.post('/request-promotion', data={'requested_role': 'inventory_manager', 'reason': ''}, follow_redirects=True)
    assert b"A reason / justification is required" in res_empty.data

    # 2. Request with valid reason should succeed
    res_ok = staff_client.post('/request-promotion', data={'requested_role': 'inventory_manager', 'reason': 'Valid reason for manager role.'}, follow_redirects=True)
    assert b"submitted to Administrator" in res_ok.data

    # 3. Requesting again while pending should fail (duplicate guard)
    res_dup = staff_client.post('/request-promotion', data={'requested_role': 'inventory_manager', 'reason': 'Another justification.'}, follow_redirects=True)
    assert b"You already have a pending request" in res_dup.data

def test_role_request_cancel_flow(staff_client):
    from inventory_app.database import get_db
    db = get_db()
    db.role_requests.delete_many({})

    # 1. Submit request
    res_ok = staff_client.post('/request-promotion', data={'requested_role': 'inventory_manager', 'reason': 'I want to help manage the stocks.'}, follow_redirects=True)
    assert res_ok.status_code == 200
    
    req = db.role_requests.find_one({"status": "PENDING"})
    assert req is not None
    req_id = str(req["_id"])

    # 2. Cancel/withdraw request
    res_cancel = staff_client.post(f'/requests/{req_id}/cancel', follow_redirects=True)
    assert res_cancel.status_code == 200
    assert b"Role request cancelled successfully" in res_cancel.data

    # Verify status changed to CANCELLED in DB
    req_cancelled = db.role_requests.find_one({"_id": req["_id"]})
    assert req_cancelled["status"] == "CANCELLED"

def test_role_request_audit_logging(staff_client, admin_client):
    from inventory_app.database import get_db
    db = get_db()
    db.role_requests.delete_many({})
    db.audit_logs.delete_many({})

    # 1. Submit
    staff_client.post('/request-promotion', data={'requested_role': 'inventory_manager', 'reason': 'Audit test reason.'}, follow_redirects=True)
    submit_log = db.audit_logs.find_one({"action_type": "role_request_submitted"})
    assert submit_log is not None
    assert submit_log["details"]["requested_role"] == "inventory_manager"

    req = db.role_requests.find_one({"status": "PENDING"})
    req_id = str(req["_id"])

    # 2. Approve
    admin_client.post(f'/users/requests/{req_id}/approve', data={'admin_comment': 'Audit approve comment'}, follow_redirects=True)
    approve_log = db.audit_logs.find_one({"action_type": "role_request_approved"})
    assert approve_log is not None
    assert approve_log["details"]["admin_comment"] == "Audit approve comment"
