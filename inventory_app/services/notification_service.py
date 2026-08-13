from datetime import datetime, timezone
from bson.objectid import ObjectId
from inventory_app.database import get_db

def sync_low_stock_notifications():
    """Identifies active products with stock <= min_stock and generates alert notifications."""
    db = get_db()
    products = list(db.products.find({"is_active": True}))
    now = datetime.now(timezone.utc)

    for p in products:
        name = p.get("product_name")
        qty = float(p.get("quantity", 0))
        min_qty = float(p.get("minimum_stock", p.get("min_stock", 5)))

        if qty <= min_qty:
            alert_type = "OUT_OF_STOCK" if qty == 0 else "LOW_STOCK"
            # Check if an unread notification already exists for this product
            existing = db.notifications.find_one({
                "product_name": name,
                "is_read": False,
                "type": alert_type
            })
            if not existing:
                msg = f"Product '{name}' is out of stock (0 remaining)!" if qty == 0 else f"Product '{name}' stock is low ({qty} left, minimum {min_qty})."
                db.notifications.insert_one({
                    "product_name": name,
                    "type": alert_type,
                    "message": msg,
                    "quantity": qty,
                    "min_stock": min_qty,
                    "is_read": False,
                    "created_at": now
                })

def get_notifications(limit: int = 50) -> list:
    sync_low_stock_notifications()
    db = get_db()
    notes = list(db.notifications.find().sort("created_at", -1).limit(limit))
    for n in notes:
        n["_id"] = str(n["_id"])
    return notes

def get_unread_notifications_count() -> int:
    sync_low_stock_notifications()
    db = get_db()
    return db.notifications.count_documents({"is_read": False})

def mark_notification_as_read(notification_id: str) -> bool:
    db = get_db()
    try:
        res = db.notifications.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}}
        )
        return res.modified_count > 0
    except Exception:
        return False

def mark_all_notifications_as_read() -> int:
    db = get_db()
    res = db.notifications.update_many(
        {"is_read": False},
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}}
    )
    return res.modified_count
