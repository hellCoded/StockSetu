from inventory_app import create_app
from werkzeug.security import generate_password_hash
app = create_app()
with app.app_context():
    from inventory_app.database import get_db
    db = get_db()
    # Reset admin password
    result = db.users.update_one(
        {"role": "admin"},
        {"$set": {
            "password_hash": generate_password_hash("Admin@123456"),
            "employee_id_lower": "emp-0001",
            "name_lower": "system administrator",
            "email_lower": "admin@inventory.local"
        }}
    )
    print(f"Admin password reset. Matched: {result.matched_count}, Modified: {result.modified_count}")
    
    # Also fix all staff users - add missing _lower fields
    all_users = list(db.users.find({}))
    for u in all_users:
        updates = {}
        if "employee_id_lower" not in u:
            updates["employee_id_lower"] = u.get("employee_id", "").lower()
        if "name_lower" not in u:
            updates["name_lower"] = u.get("name", "").lower()
        if "email_lower" not in u:
            updates["email_lower"] = u.get("email", "").lower()
        if updates:
            db.users.update_one({"_id": u["_id"]}, {"$set": updates})
            print(f"Fixed _lower fields for {u.get('employee_id', 'unknown')}")
    
    # Verify
    from werkzeug.security import check_password_hash
    admin = db.users.find_one({"role": "admin"})
    print(f"\nVerify Admin@123456: {check_password_hash(admin['password_hash'], 'Admin@123456')}")
    print(f"employee_id_lower: {admin.get('employee_id_lower')}")
