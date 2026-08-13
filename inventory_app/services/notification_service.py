"""Notification service stub — in-memory for now."""
from datetime import datetime, timezone
from inventory_app.database import get_db

_notifications = []


def sync_low_stock_notifications():
    """Create notifications for low-stock products."""
    db = get_db()
    products = list(db.products.find({"is_active": True}))
    for p in products:
        qty = float(p.get("quantity", 0))
        min_stock = float(p.get("minimum_stock", 0))
        if qty > 0 and qty < min_stock:
            name = p.get("product_name", "")
            if not any(n["product_name"] == name and not n.get("read") for n in _notifications):
                _notifications.append({
                    "product_name": name,
                    "message": f"Low stock: {name} — {qty} remaining (min {min_stock})",
                    "read": False,
                    "created_at": datetime.now(timezone.utc),
                })
        elif qty <= 0:
            name = p.get("product_name", "")
            if not any(n["product_name"] == name and not n.get("read") for n in _notifications):
                _notifications.append({
                    "product_name": name,
                    "message": f"Out of stock: {name}",
                    "read": False,
                    "created_at": datetime.now(timezone.utc),
                })


def get_notifications(limit=50):
    """Return recent notifications, newest first."""
    return sorted(_notifications, key=lambda n: n["created_at"], reverse=True)[:limit]


def get_unread_notifications_count():
    """Count unread notifications."""
    return sum(1 for n in _notifications if not n.get("read"))


def mark_notification_read(index: int):
    """Mark a notification as read by index."""
    if 0 <= index < len(_notifications):
        _notifications[index]["read"] = True


def mark_all_read():
    """Mark all notifications as read."""
    for n in _notifications:
        n["read"] = True
