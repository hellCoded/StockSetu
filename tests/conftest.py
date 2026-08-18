import pytest
import mongomock
from inventory_app import create_app, cache_flush
from config import TestConfig
from inventory_app.database import init_db
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone

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
    
    # Seed users in mock db
    db = mock_mongo['inventory_test_db']
    now = datetime.now(timezone.utc)
    
    db.users.insert_many([
        {
            "username": "testadmin",
            "email": "admin@test.com",
            "password_hash": generate_password_hash("AdminPass123"),
            "role": "admin",
            "is_active": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "username": "testmanager",
            "email": "manager@test.com",
            "password_hash": generate_password_hash("ManagerPass123"),
            "role": "inventory_manager",
            "is_active": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "username": "teststaff",
            "email": "staff@test.com",
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
    user = db.users.find_one({"username": "testadmin"})
    with client.session_transaction() as sess:
        sess['user_id'] = str(user['_id'])
        sess['username'] = 'testadmin'
        sess['email'] = 'admin@test.com'
        sess['role'] = 'admin'
    return client

@pytest.fixture
def manager_client(app, mock_mongo):
    client = app.test_client()
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"username": "testmanager"})
    with client.session_transaction() as sess:
        sess['user_id'] = str(user['_id'])
        sess['username'] = 'testmanager'
        sess['email'] = 'manager@test.com'
        sess['role'] = 'inventory_manager'
    return client

@pytest.fixture
def staff_client(app, mock_mongo):
    client = app.test_client()
    db = mock_mongo['inventory_test_db']
    user = db.users.find_one({"username": "teststaff"})
    with client.session_transaction() as sess:
        sess['user_id'] = str(user['_id'])
        sess['username'] = 'teststaff'
        sess['email'] = 'staff@test.com'
        sess['role'] = 'staff'
    return client
