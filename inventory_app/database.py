import logging
import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

db_client = None
current_db = None

def _mock_enabled(app=None) -> bool:
    """In-memory (mongomock) fallback is only allowed for tests or explicit opt-in.

    In production a silent fallback would create an EMPTY ephemeral database,
    making the app look healthy while all data is lost on restart.
    """
    if app is not None and app.config.get('TESTING', False):
        return True
    return os.environ.get('MOCK_MONGO', '').strip().lower() in ('1', 'true', 'yes')

# Deferred DB setup: indexes + admin seeding run at most once per process
# (serverless instances reuse the connection pool across warm requests).
_db_setup_done = False


def init_db(app, custom_client=None):
    """
    Initialize PyMongo database connection.

    Connection is LAZY: no network I/O happens here, so Vercel cold starts
    boot fast. The MongoClient constructor only resolves config; the actual
    handshake occurs on the first DB operation. Index creation and admin
    seeding are deferred to get_db() and run once per process.
    Supports injecting custom_client (e.g., mongomock) for unit testing.
    """
    global db_client, current_db

    if custom_client is not None:
        db_client = custom_client
        db_name = app.config.get('DATABASE_NAME', 'inventory_db')
        current_db = db_client[db_name]
        _setup_db_once(current_db)
    else:
        mongo_uri = app.config.get('MONGO_URI', 'mongodb://localhost:27017/inventory_db')
        db_name = app.config.get('DATABASE_NAME', 'inventory_db')
        db_client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
            maxPoolSize=10,
            minPoolSize=0,
            maxIdleTimeMS=10000,
            retryWrites=True,
            retryReads=True,
        )
        current_db = db_client[db_name]

    return current_db


def _setup_db_once(current_db):
    """Run index creation + admin seeding exactly once per process."""
    global _db_setup_done
    if _db_setup_done:
        return
    try:
        init_db_indexes(current_db)
        seed_default_admin(current_db)
    finally:
        _db_setup_done = True


def get_db():
    """Retrieve active MongoDB database instance (lazy connect on first use)."""
    global db_client, current_db
    if current_db is None:
        mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/inventory_db')
        db_name = os.environ.get('DATABASE_NAME', 'inventory_db')
        try:
            db_client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=20000,
                maxPoolSize=10,
                minPoolSize=0,
                maxIdleTimeMS=10000,
                retryWrites=True,
                retryReads=True,
            )
            db_client.admin.command('ping')
            current_db = db_client[db_name]
            _setup_db_once(current_db)
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            if _mock_enabled():
                logger.warning(f"Could not connect to live MongoDB server ({e}). Using in-memory database fallback.")
                import mongomock
                db_client = mongomock.MongoClient()
                current_db = db_client[db_name]
                _setup_db_once(current_db)
            else:
                logger.error(f"Could not connect to MongoDB at {mongo_uri}.")
                raise RuntimeError(
                    f"Could not connect to MongoDB at {mongo_uri}. Check MONGO_URI / DATABASE_NAME."
                ) from e
    return current_db

def init_db_indexes(db):
    """Create MongoDB indexes for performance and unique constraint enforcement."""
    try:
        # Users indexes
        db.users.create_index([("username", ASCENDING)], unique=True)
        db.users.create_index([("email", ASCENDING)], unique=True)
        
        # Clean up any stale unique indexes on products (only product_name should be unique)
        try:
            index_info = db.products.index_information()
            for idx_name, idx_spec in index_info.items():
                if idx_name != "_id_":
                    is_unique = idx_spec.get("unique", False)
                    key_fields = [k[0] for k in idx_spec.get("key", [])]
                    if is_unique and key_fields != ["product_name"]:
                        logger.warning(f"Dropping stale unique index '{idx_name}' on products collection.")
                        db.products.drop_index(idx_name)
        except Exception as idx_err:
            logger.warning(f"Could not inspect/drop old indexes: {idx_err}")

        # Products indexes (product_name is the only unique business identifier)
        db.products.create_index([("product_name", ASCENDING)], unique=True)
        db.products.create_index([("is_active", ASCENDING), ("product_name", ASCENDING)])
        db.products.create_index([("is_active", ASCENDING), ("updated_at", DESCENDING)])
        db.products.create_index([("is_active", ASCENDING), ("category", ASCENDING)])
        db.products.create_index([("is_active", ASCENDING), ("location", ASCENDING)])
        db.products.create_index([("is_active", ASCENDING), ("quantity", ASCENDING)])
        
        # Inventory transactions indexes
        db.inventory_transactions.create_index([("product_name", ASCENDING)])
        db.inventory_transactions.create_index([("product_name", ASCENDING), ("transaction_type", ASCENDING)])
        db.inventory_transactions.create_index([("created_at", DESCENDING)])
        db.inventory_transactions.create_index([("transaction_type", ASCENDING)])
        
        # Audit logs indexes
        db.audit_logs.create_index([("created_at", DESCENDING)])
        db.audit_logs.create_index([("performed_by", ASCENDING)])

        # Clean up stale unique indexes on invoices (e.g. legacy invoice_number_1)
        try:
            index_info = db.invoices.index_information()
            for idx_name, idx_spec in index_info.items():
                if idx_name != "_id_":
                    is_unique = idx_spec.get("unique", False)
                    key_fields = [k[0] for k in idx_spec.get("key", [])]
                    if is_unique and key_fields != ["bill_number"]:
                        logger.warning(f"Dropping stale unique index '{idx_name}' on invoices collection.")
                        db.invoices.drop_index(idx_name)
        except Exception as idx_err:
            logger.warning(f"Could not inspect/drop old invoices indexes: {idx_err}")

        # Invoice (billing) indexes
        db.invoices.create_index([("bill_number", ASCENDING)], unique=True)
        db.invoices.create_index([("created_at", DESCENDING)])
        db.invoices.create_index([("customer_name", ASCENDING)])
        db.invoices.create_index([("customer_phone", ASCENDING)])
        db.invoices.create_index([("payment_status", ASCENDING), ("created_at", DESCENDING)])
        db.invoices.create_index([("created_by", ASCENDING), ("created_at", DESCENDING)])

        # Bill payments indexes
        db.bill_payments.create_index([("bill_number", ASCENDING)])
        db.bill_payments.create_index([("bill_id", ASCENDING)])

        # Audit logs — compound indexes for bill lookups
        db.audit_logs.create_index([("target_resource", ASCENDING), ("created_at", DESCENDING)])

    except Exception as e:
        logger.error(f"Error initializing indexes: {e}")

def seed_default_admin(db):
    """Seed initial default administrator account if no admin exists."""
    try:
        admin_user = db.users.find_one({"role": "admin"})
        if not admin_user:
            now = datetime.now(timezone.utc)
            db.users.insert_one({
                "username": "admin",
                "email": "admin@inventory.local",
                "password_hash": generate_password_hash("Admin@123456"),
                "role": "admin",
                "is_active": True,
                "created_at": now,
                "updated_at": now
            })
            logger.info("Default administrator account created (admin / Admin@123456)")
    except Exception as e:
        logger.error(f"Error seeding default admin user: {e}")
