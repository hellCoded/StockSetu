from datetime import datetime, timezone
from inventory_app.database import get_db

def log_audit(action_type: str, performed_by: str, target_resource: str = None, details: dict = None):
    """
    Records an action into the audit_logs MongoDB collection.
    """
    db = get_db()
    audit_doc = {
        "action_type": action_type,
        "performed_by": performed_by or "System",
        "target_resource": target_resource or "",
        "details": details or {},
        "created_at": datetime.now(timezone.utc)
    }
    try:
        db.audit_logs.insert_one(audit_doc)
    except Exception as e:
        print(f"Warning: Audit log insertion failed: {e}")
