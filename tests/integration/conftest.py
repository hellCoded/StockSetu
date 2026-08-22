"""Integration test configuration using real MongoDB."""
import os
import pytest
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from werkzeug.security import generate_password_hash
from inventory_app import create_app
from config import Config
from inventory_app.database import init_db_indexes, seed_default_admin


# Integration test database name (configurable via env)
INTEGRATION_DB_NAME = os.getenv('MONGO_INTEGRATION_DB', 'stocksetu_integration_test')
MONGO_URI = os.getenv('MONGO_INTEGRATION_URI', 'mongodb://localhost:27017')


def _check_mongo_available():
    """Check if MongoDB is available for integration tests."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError):
        return False


MONGO_AVAILABLE = _check_mongo_available()


@pytest.fixture(scope="session")
def mongo_client():
    """Session-scoped MongoDB client for integration tests."""
    if not MONGO_AVAILABLE:
        pytest.skip("MongoDB not available for integration tests")
    
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    yield client
    client.close()


@pytest.fixture(scope="function")
def integration_db(mongo_client):
    """Function-scoped database for integration tests with cleanup."""
    db = mongo_client[INTEGRATION_DB_NAME]
    
    # Clean up collections before test
    collections_to_clean = [
        'users', 'products', 'invoices', 'inventory_transactions',
        'bill_payments', 'pos_drafts', 'audit_logs', 'role_requests'
    ]
    for coll in collections_to_clean:
        db[coll].delete_many({})
    
    # Create indexes
    init_db_indexes(db)
    seed_default_admin(db)
    
    # Ensure test users exist
    from werkzeug.security import generate_password_hash
    now = datetime.now(timezone.utc)
    
    test_users = [
        {
            "employee_id": "STF-INT-01",
            "employee_id_lower": "stf-int-01",
            "name": "Integration Staff",
            "name_lower": "integration staff",
            "email": "staffint@test.com",
            "email_lower": "staffint@test.com",
            "password_hash": generate_password_hash("StaffPass123"),
            "role": "staff",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "employee_id": "MGR-INT-01",
            "employee_id_lower": "mgr-int-01",
            "name": "Integration Manager",
            "name_lower": "integration manager",
            "email": "mgrint@test.com",
            "email_lower": "mgrint@test.com",
            "password_hash": generate_password_hash("ManagerPass123"),
            "role": "inventory_manager",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    ]
    for user in test_users:
        if not db.users.find_one({"employee_id": user["employee_id"]}):
            db.users.insert_one(user)
    
    yield db
    
    # Clean up after test
    collections_to_clean = [
        'users', 'products', 'invoices', 'inventory_transactions',
        'bill_payments', 'pos_drafts', 'audit_logs', 'role_requests'
    ]
    for coll in collections_to_clean:
        db[coll].delete_many({})


@pytest.fixture(scope="function")
def integration_app(integration_db):
    """Flask app configured with real MongoDB integration database."""
    # Set environment variables for get_db() to use the integration database
    os.environ['MONGO_URI'] = f"{MONGO_URI}/{INTEGRATION_DB_NAME}"
    os.environ['DATABASE_NAME'] = INTEGRATION_DB_NAME
    
    class IntegrationConfig(Config):
        TESTING = True
        MONGO_URI = f"{MONGO_URI}/{INTEGRATION_DB_NAME}"
        DATABASE_NAME = INTEGRATION_DB_NAME
        SECRET_KEY = 'integration-test-secret-key'
        SESSION_COOKIE_SECURE = False
        WTF_CSRF_ENABLED = False
        RATE_LIMIT_ENABLED = True
    
    app = create_app(IntegrationConfig)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATE_LIMIT_ENABLED'] = True
    
    with app.app_context():
        # Ensure indexes are created (already done in integration_db fixture)
        pass
    
    yield app
    
    # Restore environment variables
    os.environ.pop('MONGO_URI', None)
    os.environ.pop('DATABASE_NAME', None)


@pytest.fixture(scope="function")
def integration_client(integration_app):
    """Test client for integration tests."""
    return integration_app.test_client()


@pytest.fixture(scope="function")
def integration_admin_client(integration_client, integration_db):
    """Authenticated admin client for integration tests."""
    # Login as admin (seeded by seed_default_admin)
    integration_client.post('/login', data={
        'identifier': 'emp-0001',
        'password': 'Admin@123456'
    }, follow_redirects=True)
    return integration_client


@pytest.fixture(scope="function")
def integration_staff_client(integration_client, integration_db):
    """Authenticated staff client for integration tests."""
    integration_client.post('/login', data={
        'identifier': 'STF-INT-01',
        'password': 'StaffPass123'
    }, follow_redirects=True)
    return integration_client


def pytest_configure(config):
    """Register integration test marker."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests requiring MongoDB"
    )


# Skip integration tests entirely if MongoDB unavailable
def pytest_collection_modifyitems(config, items):
    if not MONGO_AVAILABLE:
        skip_integration = pytest.mark.skip(reason="MongoDB not available")
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip_integration)