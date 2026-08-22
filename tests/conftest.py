import pytest
import re
import mongomock
from inventory_app import create_app, cache_flush
from config import TestConfig
from inventory_app.database import init_db
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone
from inventory_app.routes.auth_routes import _LOGIN_RATE_LIMIT_STATE

@pytest.fixture(autouse=True)
def clear_login_rate_limit():
    """Clear login rate limit state before each test."""
    _LOGIN_RATE_LIMIT_STATE.clear()
    yield
    _LOGIN_RATE_LIMIT_STATE.clear()

@pytest.fixture
def mock_mongo():
    client = mongomock.MongoClient()
    return client

@pytest.fixture
def app(mock_mongo):
    cache_flush()
    app = create_app(TestConfig, custom_mongo_client=mock_mongo)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    # Enable rate limiting for tests that need it
    app.config['RATE_LIMIT_ENABLED'] = True
    
    # Seed users in mock db
    db = mock_mongo['inventory_test_db']
    now = datetime.now(timezone.utc)
    
    db.users.insert_many([
        {
            "employee_id": "ADM-001",
            "employee_id_lower": "adm-001",
            "name": "Test Admin",
            "name_lower": "test admin",
            "email": "admin@test.com",
            "email_lower": "admin@test.com",
            "password_hash": generate_password_hash("AdminPass123"),
            "role": "admin",
            "is_active": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "employee_id": "MGR-001",
            "employee_id_lower": "mgr-001",
            "name": "Test Manager",
            "name_lower": "test manager",
            "email": "manager@test.com",
            "email_lower": "manager@test.com",
            "password_hash": generate_password_hash("ManagerPass123"),
            "role": "inventory_manager",
            "is_active": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "employee_id": "STF-001",
            "employee_id_lower": "stf-001",
            "name": "Test Staff",
            "name_lower": "test staff",
            "email": "staff@test.com",
            "email_lower": "staff@test.com",
            "password_hash": generate_password_hash("StaffPass123"),
            "role": "staff",
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }
    ])
    
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def admin_client(app, mock_mongo):
    client = app.test_client()
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "ADM-001"})
    with client.session_transaction() as sess:
        sess['user_id'] = str(user['_id'])
        sess['employee_id'] = user.get('employee_id', 'ADM-001')
        sess['name'] = user.get('name', 'Test Admin')
        sess['email'] = 'admin@test.com'
        sess['role'] = 'admin'
    return client

@pytest.fixture
def manager_client(app, mock_mongo):
    client = app.test_client()
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "MGR-001"})
    with client.session_transaction() as sess:
        sess['user_id'] = str(user['_id'])
        sess['employee_id'] = user.get('employee_id', 'MGR-001')
        sess['name'] = user.get('name', 'Test Manager')
        sess['email'] = 'manager@test.com'
        sess['role'] = 'inventory_manager'
    return client

@pytest.fixture
def staff_client(app, mock_mongo):
    client = app.test_client()
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"employee_id": "STF-001"})
    with client.session_transaction() as sess:
        sess['user_id'] = str(user['_id'])
        sess['employee_id'] = user.get('employee_id', 'STF-001')
        sess['name'] = user.get('name', 'Test Staff')
        sess['email'] = 'staff@test.com'
        sess['role'] = 'staff'
    return client
