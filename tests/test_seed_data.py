import sys
import os
import pytest
from werkzeug.security import check_password_hash
from inventory_app.services.auth_service import authenticate_user

# Ensure scripts is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.seed_dummy_data import run_seeder, TEST_PASSWORD

def test_seed_and_clean_workflow(monkeypatch, mock_mongo, app):
    # 1. Setup mock database and force MongoClient to return our shared mock_mongo client
    import inventory_app.database
    orig_init_db = inventory_app.database.init_db
    monkeypatch.setattr(inventory_app.database, "current_db", mock_mongo['inventory_db'])
    monkeypatch.setattr(inventory_app.database, "db_client", mock_mongo)
    monkeypatch.setattr(inventory_app.database, "init_db", lambda app, custom_client=None: orig_init_db(app, custom_client=mock_mongo))
    monkeypatch.setattr("inventory_app.init_db", lambda app, custom_client=None: orig_init_db(app, custom_client=mock_mongo))
    
    db = inventory_app.database.get_db()
    
    # Ensure safety guard matches development environment
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("MOCK_MONGO", "1")

    # 2. Run clean run of seeding (100 products, 100 users)
    monkeypatch.setattr(sys, "argv", [
        "seed_dummy_data.py", 
        "--products", "100", 
        "--users", "100"
    ])
    
    run_seeder()
    db = inventory_app.database.get_db()

    # Assert correct counts are inserted
    seeded_products = list(db.products.find({"product_name": {"$regex": "^TEST-SKU-"}}))
    seeded_users = list(db.users.find({"email": {"$regex": "@example.test$"}}))

    assert len(seeded_products) == 100
    assert len(seeded_users) == 100

    # Assert role distribution matches specification (5 admins, 15 managers, 80 staff)
    admins = [u for u in seeded_users if u["role"] == "admin"]
    managers = [u for u in seeded_users if u["role"] == "inventory_manager"]
    staff = [u for u in seeded_users if u["role"] == "staff"]

    assert len(admins) == 5
    assert len(managers) == 15
    assert len(staff) == 80

    # Assert active/inactive split (approx 10% inactive, every 10th user)
    inactive_users = [u for u in seeded_users if not u.get("is_active", True)]
    assert len(inactive_users) == 10  # 10 out of 100 users deactivated

    # Assert at least one seeded product is below min-stock threshold (hardcoded 5)
    low_stock_products = [
        p for p in seeded_products 
        if float(p.get("quantity", 0)) <= 5
    ]
    assert len(low_stock_products) >= 1

    # Assert every seeded user's password verifies correctly against TEST_PASSWORD
    for user in seeded_users:
        # Verify using check_password_hash
        assert check_password_hash(user["password_hash"], TEST_PASSWORD)
        
        # Verify using application's own authenticate_user function
        with app.app_context():
            identifier = user.get("employee_id") or user.get("username")
            success, msg, auth_user = authenticate_user(identifier, TEST_PASSWORD)
            assert success, f"Failed to authenticate seeded user {identifier}: {msg}"
            assert auth_user["email"] == user["email"]

    # 3. Test Idempotency (run seeding again, verify counts do not change)
    monkeypatch.setattr(sys, "argv", [
        "seed_dummy_data.py", 
        "--products", "100", 
        "--users", "100"
    ])
    
    run_seeder()

    assert db.products.count_documents({"product_name": {"$regex": "^TEST-SKU-"}}) == 100
    assert db.users.count_documents({"email": {"$regex": "@example.test$"}}) == 100

    # 4. Test Clean Rollback (--clean removes only seeded records)
    # Let's insert a real (non-seeded) product & user to verify they are NOT deleted
    db.products.insert_one({
        "product_name": "REAL-PRODUCT-DO-NOT-DELETE",
        "category": "Cement",
        "quantity": 10.0,
        "price": 100.0,
        "is_active": True
    })
    db.users.insert_one({
        "employee_id": "EMP-REAL-01",
        "username": "realuser",
        "email": "realuser@company.com",
        "password_hash": "somehash",
        "role": "staff",
        "is_active": True
    })

    monkeypatch.setattr(sys, "argv", [
        "seed_dummy_data.py", 
        "--clean"
    ])
    
    run_seeder()

    # Seeded records must be gone
    assert db.products.count_documents({"product_name": {"$regex": "^TEST-SKU-"}}) == 0
    assert db.users.count_documents({"email": {"$regex": "@example.test$"}}) == 0
    assert db.inventory_transactions.count_documents({"product_name": {"$regex": "^TEST-SKU-"}}) == 0

    # Real records must still exist
    assert db.products.count_documents({"product_name": "REAL-PRODUCT-DO-NOT-DELETE"}) == 1
    assert db.users.count_documents({"$or": [{"username": "realuser"}, {"employee_id": "EMP-REAL-01"}]}) == 1

    # Cleanup mock data
    db.products.delete_one({"product_name": "REAL-PRODUCT-DO-NOT-DELETE"})
    db.users.delete_one({"$or": [{"username": "realuser"}, {"employee_id": "EMP-REAL-01"}]})


def test_safety_guard(monkeypatch, mock_mongo):
    import inventory_app.database
    orig_init_db = inventory_app.database.init_db
    monkeypatch.setattr(inventory_app.database, "current_db", mock_mongo['inventory_db'])
    monkeypatch.setattr(inventory_app.database, "db_client", mock_mongo)
    monkeypatch.setattr(inventory_app.database, "init_db", lambda app, custom_client=None: orig_init_db(app, custom_client=mock_mongo))
    monkeypatch.setattr("inventory_app.init_db", lambda app, custom_client=None: orig_init_db(app, custom_client=mock_mongo))
    
    # Set environment variables to simulate production
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("APP_ENV", "production")

    monkeypatch.setattr(sys, "argv", [
        "seed_dummy_data.py", 
        "--products", "10", 
        "--users", "10"
    ])

    # Script should raise SystemExit(1)
    with pytest.raises(SystemExit) as excinfo:
        run_seeder()
    assert excinfo.value.code == 1
