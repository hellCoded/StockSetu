from inventory_app import create_app
from werkzeug.security import check_password_hash
app = create_app()
with app.app_context():
    from inventory_app.database import get_db
    db = get_db()
    admin = db.users.find_one({'role':'admin'})
    if admin:
        print(f"Employee ID: {admin.get('employee_id')}")
        print(f"Employee ID Lower: {admin.get('employee_id_lower', 'N/A')}")
        print(f"Email: {admin.get('email')}")
        print(f"Hash prefix: {admin.get('password_hash')[:50]}")
        print(f"Check Admin@123456: {check_password_hash(admin['password_hash'], 'Admin@123456')}")
    staff = db.users.find_one({'role':'staff'})
    if staff:
        print(f"\nStaff ID: {staff.get('employee_id')}")
        print(f"Staff Email: {staff.get('email')}")
        print(f"Staff Hash prefix: {staff.get('password_hash')[:50]}")
