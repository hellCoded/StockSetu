import logging
from datetime import datetime, timezone
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from inventory_app.database import get_db

logger = logging.getLogger(__name__)

def register_user(username: str, email: str, password: str, role: str = "staff", name: str = "", surname: str = "") -> tuple[bool, str, dict]:
    """Registers a new user in MongoDB."""
    db = get_db()
    
    clean_username = username.strip()
    clean_email = email.strip().lower()
    clean_name = name.strip()
    clean_surname = surname.strip() if surname else ""
    full_name = f"{clean_name} {clean_surname}".strip() if clean_surname else clean_name
    
    # Check duplicate username
    if db.users.find_one({"username": {"$regex": f"^{re_escape(clean_username)}$", "$options": "i"}}):
        return False, "Username is already taken.", {}
        
    # Check duplicate email
    if db.users.find_one({"email": clean_email}):
        return False, "Email address is already registered.", {}
        
    valid_roles = ["admin", "inventory_manager", "staff"]
    assigned_role = role if role in valid_roles else "staff"
    
    now = datetime.now(timezone.utc)
    user_doc = {
        "username": clean_username,
        "name": full_name,
        "email": clean_email,
        "password_hash": generate_password_hash(password),
        "role": assigned_role,
        "is_active": True,
        "last_active_at": now,
        "created_at": now,
        "updated_at": now
    }
    
    try:
        result = db.users.insert_one(user_doc)
        user_doc["_id"] = str(result.inserted_id)
        return True, "Registration successful.", user_doc
    except Exception as e:
        return False, f"Failed to create user account: {str(e)}", {}

def set_user_active_status(user_id: str, is_active: bool):
    """Sets user is_active boolean state in database."""
    db = get_db()
    try:
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_active": is_active, "updated_at": datetime.now(timezone.utc)}}
        )
    except Exception as e:
        logger.error(f"Failed to set user active status: {e}")

def record_user_activity(user_id: str):
    """Updates the last_active_at timestamp for a user and marks them active."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return
    db = get_db()
    try:
        now = datetime.now(timezone.utc)
        db.users.update_one(
            {"_id": ObjectId(uid_str)},
            {"$set": {"last_active_at": now, "updated_at": now}}
        )
    except Exception as e:
        logger.error(f"Failed to record user activity: {e}")

def deactivate_inactive_users(inactivity_hours: float = 12.0) -> int:
    """
    Finds all active users who have been inactive/offline for more than `inactivity_hours`
    and marks them as inactive (is_active = False).
    Returns count of users deactivated.
    """
    from datetime import timedelta
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=inactivity_hours)
    try:
        result = db.users.update_many(
            {
                "is_active": True,
                "$or": [
                    {"last_active_at": {"$lt": cutoff}},
                    {"last_active_at": {"$exists": False}, "updated_at": {"$lt": cutoff}},
                    {"last_active_at": {"$exists": False}, "updated_at": {"$exists": False}, "created_at": {"$lt": cutoff}}
                ]
            },
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count
    except Exception as e:
        logger.error(f"Failed to deactivate inactive users: {e}")
        return 0

def authenticate_user(identifier: str, password: str) -> tuple[bool, str, dict]:
    """Authenticates user by username or email."""
    db = get_db()
    clean_id = identifier.strip()
    
    user = db.users.find_one({
        "$or": [
            {"username": clean_id},
            {"email": clean_id.lower()}
        ]
    })
    
    if not user:
        return False, "Account not found. Please register an account first.", {}
        
    if check_password_hash(user.get("password_hash", ""), password):
        now = datetime.now(timezone.utc)
        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"is_active": True, "last_active_at": now, "updated_at": now}}
        )
        user["is_active"] = True
        user["last_active_at"] = now
        user["_id"] = str(user["_id"])
        return True, "Login successful.", user
        
    return False, "Invalid username/email or password.", {}

def get_all_users():
    """Retrieves all users for admin management."""
    db = get_db()
    users = list(db.users.find().sort("created_at", -1))
    for u in users:
        u["_id"] = str(u["_id"])
    return users

def get_user_by_id(user_id: str):
    """Retrieves user by string ID."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return None
    db = get_db()
    try:
        user = db.users.find_one({"_id": ObjectId(uid_str)})
        if user:
            user["_id"] = str(user["_id"])
        return user
    except Exception:
        return None

def update_user_role(user_id: str, new_role: str) -> tuple[bool, str]:
    """Updates user role (Admin only)."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return False, "Invalid user ID."
    db = get_db()
    valid_roles = ["admin", "inventory_manager", "staff"]
    if new_role not in valid_roles:
        return False, "Invalid role specified."
        
    try:
        result = db.users.update_one(
            {"_id": ObjectId(uid_str)},
            {"$set": {"role": new_role, "updated_at": datetime.now(timezone.utc)}}
        )
        if result.modified_count > 0 or result.matched_count > 0:
            return True, f"User role updated to {new_role}."
        return False, "User not found."
    except Exception as e:
        return False, f"Failed to update role: {str(e)}"

def toggle_user_active(user_id: str) -> tuple[bool, str, bool]:
    """Toggles user active state (Admin only)."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return False, "Invalid user ID.", False
    db = get_db()
    try:
        user = db.users.find_one({"_id": ObjectId(uid_str)})
        if not user:
            return False, "User not found.", False
            
        new_status = not user.get("is_active", True)
        db.users.update_one(
            {"_id": ObjectId(uid_str)},
            {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc)}}
        )
        status_str = "activated" if new_status else "deactivated"
        return True, f"User account has been {status_str}.", new_status
    except Exception as e:
        return False, f"Failed to update user status: {str(e)}", False

def change_password(user_id: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """Changes password for logged in user."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return False, "Invalid user ID."
    db = get_db()
    try:
        user = db.users.find_one({"_id": ObjectId(uid_str)})
        if not user:
            return False, "User not found."
            
        if not check_password_hash(user.get("password_hash", ""), old_password):
            return False, "Current password is incorrect."
            
        if len(new_password) < 6:
            return False, "New password must be at least 6 characters long."
            
        db.users.update_one(
            {"_id": ObjectId(uid_str)},
            {"$set": {
                "password_hash": generate_password_hash(new_password),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        return True, "Password changed successfully."
    except Exception as e:
        return False, f"Failed to change password: {str(e)}"

def update_user_profile_info(user_id: str, name: str, email: str) -> tuple[bool, str]:
    """Updates name and email for logged-in user profile."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return False, "Invalid user ID."
    db = get_db()
    if not email or '@' not in email:
        return False, "Please provide a valid email address."
        
    try:
        existing = db.users.find_one({"email": email.strip().lower(), "_id": {"$ne": ObjectId(uid_str)}})
        if existing:
            return False, "This email address is already registered to another account."
            
        db.users.update_one(
            {"_id": ObjectId(uid_str)},
            {"$set": {
                "name": name.strip(),
                "email": email.strip().lower(),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        return True, "Profile details updated successfully."
    except Exception as e:
        return False, f"Failed to update profile: {str(e)}"

def re_escape(text: str) -> str:
    import re
    return re.escape(text)

def create_role_request(user_id: str, username: str, email: str, requested_role: str = "inventory_manager", reason: str = "") -> tuple[bool, str]:
    """Submits a role promotion/update request from user to admin for verification."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return False, "Invalid user ID."
    db = get_db()
    valid_requested_roles = ["inventory_manager", "admin"]
    if requested_role not in valid_requested_roles:
        return False, "Invalid requested role."

    if not reason or not reason.strip():
        return False, "A reason / justification is required to submit a role request."

    try:
        existing = db.role_requests.find_one({"user_id": uid_str, "status": "PENDING"})
        if existing:
            return False, "You already have a pending request"
            
        user = db.users.find_one({"_id": ObjectId(uid_str)})
        current_role = user.get("role", "staff") if user else "staff"

        if current_role == requested_role:
            return False, f"You are already assigned the '{current_role}' role."

        now = datetime.now(timezone.utc)
        request_doc = {
            "user_id": uid_str,
            "username": username,
            "email": email,
            "current_role": current_role,
            "requested_role": requested_role,
            "reason": reason.strip(),
            "status": "PENDING",
            "created_at": now,
            "updated_at": now
        }
        db.role_requests.insert_one(request_doc)
        
        from inventory_app.services.audit_service import log_audit
        log_audit("role_request_submitted", username, target_resource=uid_str, details={"requested_role": requested_role, "reason": reason.strip()})
        
        return True, f"Role request ({requested_role.replace('_', ' ').title()}) submitted to Administrator for verification."
    except Exception as e:
        return False, f"Failed to submit role request: {str(e)}"

def cancel_role_request(request_id: str, user_id: str) -> tuple[bool, str]:
    """Withdraws/cancels a pending role request."""
    req_id_str = str(request_id) if request_id else ""
    uid_str = str(user_id) if user_id else ""
    if not req_id_str or not ObjectId.is_valid(req_id_str):
        return False, "Invalid request ID."
    db = get_db()
    try:
        req = db.role_requests.find_one({"_id": ObjectId(req_id_str)})
        if not req:
            return False, "Role request not found."
            
        if str(req.get("user_id")) != uid_str:
            return False, "You are not authorized to cancel this request."
            
        if req.get("status") != "PENDING":
            return False, "Only pending requests can be cancelled."
            
        now = datetime.now(timezone.utc)
        db.role_requests.update_one(
            {"_id": ObjectId(req_id_str)},
            {"$set": {"status": "CANCELLED", "updated_at": now}}
        )
        
        from inventory_app.services.audit_service import log_audit
        log_audit("role_request_cancelled", req.get("username"), target_resource=uid_str, details={"request_id": req_id_str})
        
        return True, "Role request cancelled successfully."
    except Exception as e:
        return False, f"Failed to cancel role request: {str(e)}"

def get_user_role_requests(user_id: str) -> list:
    """Returns all role requests submitted by the given user, sorted by created_at desc."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return []
    db = get_db()
    requests = list(db.role_requests.find({"user_id": uid_str}).sort("created_at", -1))
    for r in requests:
        r["_id"] = str(r["_id"])
    return requests

def get_user_pending_role_request(user_id: str) -> dict:
    """Returns any PENDING role request for the given user."""
    uid_str = str(user_id) if user_id else ""
    if not uid_str or not ObjectId.is_valid(uid_str):
        return None
    db = get_db()
    req = db.role_requests.find_one({"user_id": uid_str, "status": "PENDING"})
    if req:
        req["_id"] = str(req["_id"])
    return req

def get_all_pending_role_requests() -> list:
    """Returns list of all PENDING role promotion requests for Admin review."""
    db = get_db()
    requests = list(db.role_requests.find({"status": "PENDING"}).sort("created_at", -1))
    for r in requests:
        r["_id"] = str(r["_id"])
    return requests

def get_all_role_requests() -> list:
    """Returns list of all role promotion requests sorted by created_at desc."""
    db = get_db()
    requests = list(db.role_requests.find().sort("created_at", -1))
    for r in requests:
        r["_id"] = str(r["_id"])
    return requests

def get_role_requests_by_status_count() -> list:
    """Returns a list of status and count for all role requests, used for dashboard visualization."""
    db = get_db()
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    try:
        results = list(db.role_requests.aggregate(pipeline))
        return [{"status": r["_id"], "count": r["count"]} for r in results]
    except Exception:
        return []

def process_role_request(request_id: str, action: str, processed_by: str, admin_comment: str = "") -> tuple[bool, str]:
    """Approves or rejects a pending role promotion request with an optional comment."""
    req_id_str = str(request_id) if request_id else ""
    if not req_id_str or not ObjectId.is_valid(req_id_str):
        return False, "Invalid request ID."
    db = get_db()
    try:
        req = db.role_requests.find_one({"_id": ObjectId(req_id_str)})
        if not req:
            return False, "Role request not found."
            
        if req.get("status") != "PENDING":
            return False, "Role request has already been processed."
            
        now = datetime.now(timezone.utc)
        comment_str = admin_comment.strip()
        
        if action == "approve":
            user_id = str(req["user_id"])
            new_role = req.get("requested_role", "inventory_manager")
            
            success, msg = update_user_role(user_id, new_role)
            if not success:
                return False, msg
                
            db.role_requests.update_one(
                {"_id": ObjectId(req_id_str)},
                {"$set": {"status": "APPROVED", "processed_by": processed_by, "admin_comment": comment_str, "updated_at": now}}
            )
            
            from inventory_app.services.audit_service import log_audit
            log_audit("role_request_approved", processed_by, target_resource=user_id, details={"request_id": req_id_str, "admin_comment": comment_str})
            
            role_label = new_role.replace('_', ' ').title()
            return True, f"Role request approved. User '{req['username']}' is now an {role_label}."
            
        elif action == "reject":
            db.role_requests.update_one(
                {"_id": ObjectId(req_id_str)},
                {"$set": {"status": "REJECTED", "processed_by": processed_by, "admin_comment": comment_str, "updated_at": now}}
            )
            
            from inventory_app.services.audit_service import log_audit
            log_audit("role_request_rejected", processed_by, target_resource=str(req["user_id"]), details={"request_id": req_id_str, "admin_comment": comment_str})
            
            return True, f"Promotion request for user '{req['username']}' has been rejected."
        else:
            return False, "Invalid action."
    except Exception as e:
        return False, f"Failed to process role request: {str(e)}"
