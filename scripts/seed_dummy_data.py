import os
import sys
import argparse
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from bson import ObjectId

# Ensure project root is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from inventory_app import create_app
from inventory_app.database import get_db
from inventory_app.services.product_service import create_product
from inventory_app.services.auth_service import register_user

CATEGORIES = [
    'Cement',
    'Building Materials',
    'Tools & Equipment',
    'Safety Gear',
    'Plumbing',
    'Electrical',
    'Paints & Chemicals',
    'Hardware & Fasteners'
]

UNITS = {
    'Cement': 'bags',
    'Building Materials': 'pcs',
    'Tools & Equipment': 'pcs',
    'Safety Gear': 'pcs',
    'Plumbing': 'meters',
    'Electrical': 'meters',
    'Paints & Chemicals': 'liters',
    'Hardware & Fasteners': 'pcs'
}

TEST_PASSWORD = "TestPass123!"

def run_seeder():
    parser = argparse.ArgumentParser(description="Seed dummy products and users into Inventory Hub.")
    parser.add_argument('--products', type=int, default=100, help="Number of products to seed")
    parser.add_argument('--users', type=int, default=100, help="Number of users to seed")
    parser.add_argument('--clean', action='store_true', help="Remove all seeded dummy data and exit")
    parser.add_argument('--force', action='store_true', help="Bypass environment safety guards")
    args = parser.parse_args()

    # Load Flask App Context
    app = create_app()

    with app.app_context():
        db = get_db()
        db_name = app.config.get('DATABASE_NAME', 'inventory_db')
        mongo_uri = app.config.get('MONGO_URI', 'mongodb://localhost:27017/inventory_db')

        # 1. Environment Safety Guard
        flask_env = os.getenv('FLASK_ENV', '').lower()
        app_env = os.getenv('APP_ENV', '').lower()
        is_dev_or_test = flask_env in ('development', 'testing') or app_env in ('development', 'testing')

        if not is_dev_or_test and not args.force:
            print("=" * 60)
            print("ERROR: Safety Guard Blocked Execution!")
            print(f"Current FLASK_ENV: '{flask_env}', APP_ENV: '{app_env}'")
            print("Seeding is only permitted in 'development' or 'testing' environments.")
            print("To override this safety guard, run with the --force flag.")
            print("=" * 60)
            sys.exit(1)

        if args.force:
            print("=" * 60)
            print("LOUD WARNING: You are forcing the script to run!")
            print(f"Target Database URI: {mongo_uri}")
            print(f"Target Database Name: {db_name}")
            print("=" * 60)

        # 2. Cleanup Flow
        if args.clean:
            print("Cleaning up previously seeded test data...")
            prod_res = db.products.delete_many({"product_name": {"$regex": "^TEST-SKU-"}})
            user_res = db.users.delete_many({"email": {"$regex": "@example.test$"}})
            tx_res = db.inventory_transactions.delete_many({"product_name": {"$regex": "^TEST-SKU-"}})
            
            print(f"Successfully deleted {prod_res.deleted_count} products.")
            print(f"Successfully deleted {user_res.deleted_count} users.")
            print(f"Successfully deleted {tx_res.deleted_count} inventory transactions.")
            print("Cleanup completed successfully.")
            return

        # 3. Seed Products Flow
        print(f"Seeding {args.products} dummy products...")
        prod_inserted = 0
        prod_skipped = 0

        for i in range(1, args.products + 1):
            prod_name = f"TEST-SKU-{i:04d}"
            category = CATEGORIES[(i - 1) % len(CATEGORIES)]
            unit = UNITS[category]
            price = round(50.0 + (i * 27.5) % 1500.0, 2)
            gst_rate = 18.0
            hsn_code = f"H{10000+i}"
            minimum_stock = float(10 + (i * 5) % 40)
            
            # Make ~15% low stock (every 7th product)
            is_low_stock = (i % 7 == 0)
            quantity = float(minimum_stock - 5 if is_low_stock else minimum_stock + 20)
            if quantity < 0:
                quantity = 0.0

            product_data = {
                "product_name": prod_name,
                "category": category,
                "description": f"Seeded test product for {category} inventory tracking",
                "unit": unit,
                "price": price,
                "gst_rate": gst_rate,
                "hsn_code": hsn_code,
                "location": f"Aisle-{i%10 + 1}"
            }

            success, msg, _ = create_product(product_data, performed_by="System Seeder")
            if success:
                prod_inserted += 1
            elif "already exists" in msg:
                prod_skipped += 1
            else:
                print(f"Failed to seed product {prod_name}: {msg}")

        # 4. Seed Users Flow
        print(f"Seeding {args.users} dummy users...")
        user_inserted = 0
        user_skipped = 0

        # Calculate role counts based on spec proportions:
        # ~5% admin, ~15% manager, ~80% staff
        admins_target = max(1, int(args.users * 0.05))
        managers_target = max(1, int(args.users * 0.15))
        staff_target = args.users - admins_target - managers_target

        roles_list = (
            ['admin'] * admins_target +
            ['inventory_manager'] * managers_target +
            ['staff'] * staff_target
        )

        for i in range(1, args.users + 1):
            role = roles_list[i - 1]
            employee_id = f"EMP-{1000+i}"
            email = f"emp{1000+i}@example.test"
            name = f"Test {role.replace('_', ' ').title()} {i}"
            
            success, msg, user_doc = register_user(
                employee_id=employee_id,
                email=email,
                password=TEST_PASSWORD,
                role=role,
                name=name
            )

            if success:
                user_inserted += 1
                # Deactivate ~10% of users (every 10th user)
                if i % 10 == 0:
                    db.users.update_one(
                        {"_id": ObjectId(user_doc["_id"])},
                        {"$set": {"is_active": False}}
                    )
            elif "already registered" in msg or "already taken" in msg:
                user_skipped += 1
            else:
                print(f"Failed to seed user {employee_id}: {msg}")

        print("=" * 60)
        print("SEEDING SUMMARY")
        print("=" * 60)
        print(f"Products Created      : {prod_inserted}")
        print(f"Products Skipped      : {prod_skipped}")
        print(f"Users Created         : {user_inserted}")
        print(f"Users Skipped         : {user_skipped}")
        print("-" * 60)
        print(f"Shared Plaintext Pass : {TEST_PASSWORD}")
        print("=" * 60)

if __name__ == "__main__":
    run_seeder()
