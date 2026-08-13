from datetime import datetime, timezone
from bson.objectid import ObjectId
from inventory_app.database import get_db
from inventory_app.services.audit_service import log_audit

def get_all_categories() -> list:
    db = get_db()
    categories = list(db.categories.find().sort("name", 1))
    for c in categories:
        c["_id"] = str(c["_id"])
    return categories

def create_category(name: str, description: str, performed_by: str) -> tuple[bool, str, dict]:
    name = (name or '').strip()
    if not name:
        return False, "Category name is required.", {}
    if len(name) > 60:
        return False, "Category name cannot exceed 60 characters.", {}

    db = get_db()
    existing = db.categories.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}})
    if existing:
        return False, f"Category '{name}' already exists.", {}

    now = datetime.now(timezone.utc)
    cat_doc = {
        "name": name,
        "description": (description or '').strip(),
        "created_by": performed_by,
        "created_at": now,
        "updated_at": now
    }
    res = db.categories.insert_one(cat_doc)
    cat_doc["_id"] = str(res.inserted_id)
    log_audit("CATEGORY_CREATE", performed_by, name, {"description": cat_doc["description"]})
    return True, f"Category '{name}' created successfully.", cat_doc

def delete_category(category_id: str, performed_by: str) -> tuple[bool, str]:
    db = get_db()
    try:
        cat = db.categories.find_one({"_id": ObjectId(category_id)})
    except Exception:
        return False, "Invalid Category ID format."

    if not cat:
        return False, "Category not found."

    cat_name = cat["name"]
    # Check if any product is using this category
    prod_count = db.products.count_documents({"category": cat_name})
    if prod_count > 0:
        return False, f"Cannot delete category '{cat_name}' because {prod_count} product(s) are assigned to it."

    db.categories.delete_one({"_id": ObjectId(category_id)})
    log_audit("CATEGORY_DELETE", performed_by, cat_name, {})
    return True, f"Category '{cat_name}' deleted successfully."
