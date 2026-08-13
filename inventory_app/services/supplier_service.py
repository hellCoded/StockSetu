import re
from datetime import datetime, timezone
from bson.objectid import ObjectId
from inventory_app.database import get_db
from inventory_app.services.audit_service import log_audit

def get_all_suppliers() -> list:
    db = get_db()
    suppliers = list(db.suppliers.find().sort("name", 1))
    for s in suppliers:
        s["_id"] = str(s["_id"])
    return suppliers

def create_supplier(code: str, name: str, contact_person: str, phone: str, email: str, performed_by: str) -> tuple[bool, str, dict]:
    code = (code or '').strip().upper()
    name = (name or '').strip()
    contact_person = (contact_person or '').strip()
    phone = (phone or '').strip()
    email = (email or '').strip().lower()

    if not code or not name:
        return False, "Supplier Code and Supplier Name are required.", {}
    if not re.match(r'^[A-Z0-9_-]{2,20}$', code):
        return False, "Supplier Code must be 2-20 alphanumeric characters.", {}

    db = get_db()
    if db.suppliers.find_one({"code": code}):
        return False, f"Supplier code '{code}' already exists.", {}

    now = datetime.now(timezone.utc)
    sup_doc = {
        "code": code,
        "name": name,
        "contact_person": contact_person,
        "phone": phone,
        "email": email,
        "created_by": performed_by,
        "created_at": now,
        "updated_at": now
    }
    res = db.suppliers.insert_one(sup_doc)
    sup_doc["_id"] = str(res.inserted_id)
    log_audit("SUPPLIER_CREATE", performed_by, code, {"name": name})
    return True, f"Supplier '{name}' ({code}) created successfully.", sup_doc

def delete_supplier(supplier_id: str, performed_by: str) -> tuple[bool, str]:
    db = get_db()
    try:
        sup = db.suppliers.find_one({"_id": ObjectId(supplier_id)})
    except Exception:
        return False, "Invalid Supplier ID format."

    if not sup:
        return False, "Supplier not found."

    code = sup["code"]
    db.suppliers.delete_one({"_id": ObjectId(supplier_id)})
    log_audit("SUPPLIER_DELETE", performed_by, code, {"name": sup["name"]})
    return True, f"Supplier '{sup['name']}' deleted successfully."
