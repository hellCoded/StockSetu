import io
import csv
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

def get_all_users(search: str = "", role: str = "", page: int = None, per_page: int = 25, return_total: bool = False):
    """Retrieves users for admin management with optional filtering and pagination."""
    db = get_db()
    query = {}
    if search:
        import re
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"username": {"$regex": escaped, "$options": "i"}},
            {"email": {"$regex": escaped, "$options": "i"}},
            {"name": {"$regex": escaped, "$options": "i"}},
            {"surname": {"$regex": escaped, "$options": "i"}},
        ]
    if role:
        query["role"] = role.strip().lower()

    total_count = 0
    if return_total:
        total_count = db.users.count_documents(query)

    cursor = db.users.find(query).sort("created_at", -1)
    if page is not None and per_page is not None:
        effective_page = max(1, int(page or 1))
        effective_limit = max(1, int(per_page or 25))
        cursor = cursor.skip((effective_page - 1) * effective_limit).limit(effective_limit)

    users = list(cursor)
    for u in users:
        u["_id"] = str(u["_id"])

    if return_total:
        return users, total_count
    return users


def get_user_stats() -> dict:
    """Computes total counts of active, inactive, admin, manager, and staff accounts."""
    db = get_db()
    pipeline = [
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "active": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}},
            "inactive": {"$sum": {"$cond": [{"$ne": ["$is_active", True]}, 1, 0]}},
            "admins": {"$sum": {"$cond": [{"$eq": ["$role", "admin"]}, 1, 0]}},
            "managers": {"$sum": {"$cond": [{"$eq": ["$role", "inventory_manager"]}, 1, 0]}},
            "staff": {"$sum": {"$cond": [{"$eq": ["$role", "staff"]}, 1, 0]}},
        }}
    ]
    res = list(db.users.aggregate(pipeline))
    if res:
        stats = res[0]
        stats.pop("_id", None)
        return stats
    return {"total": 0, "active": 0, "inactive": 0, "admins": 0, "managers": 0, "staff": 0}


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


def import_staff_bulk(file_storage, default_password: str = "Staff@123", imported_by: str = "admin") -> tuple[bool, str, dict]:
    """
    Parses and bulk registers staff/employees from an Excel (.xlsx, .xls) or CSV file.
    Returns (success: bool, message: str, details: dict).
    """
    import io
    import csv
    import random
    from datetime import datetime, timezone
    from werkzeug.security import generate_password_hash
    from inventory_app.database import get_db

    if not file_storage or not file_storage.filename:
        return False, "No file selected. Please choose a valid Excel or CSV file.", {}

    filename = file_storage.filename.lower()
    file_bytes = file_storage.read()
    file_storage.seek(0)

    rows = []
    if filename.endswith(('.xlsx', '.xls')):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            sheet = wb.active or wb.worksheets[0]
            rows = list(sheet.iter_rows(values_only=True))
        except Exception as e:
            return False, f"Failed to read Excel workbook: {str(e)}", {}
    elif filename.endswith('.csv'):
        try:
            text_content = file_bytes.decode('utf-8-sig', errors='replace')
            csv_reader = csv.reader(io.StringIO(text_content))
            rows = [list(r) for r in csv_reader]
        except Exception as e:
            return False, f"Failed to read CSV file: {str(e)}", {}
    else:
        return False, "Unsupported file format. Please upload an Excel (.xlsx, .xls) or CSV file.", {}

    if not rows or len(rows) < 2:
        return False, "The uploaded file is empty or missing data rows.", {}

    # Identify header row & column mappings
    header = [str(cell or "").strip().lower() for cell in rows[0]]
    col_map = {}
    for idx, col in enumerate(header):
        clean_col = col.replace("_", " ").replace("-", " ")
        if any(k in clean_col for k in ['first name', 'firstname', 'employee name', 'staff name']) or clean_col == 'name':
            col_map.setdefault('name', idx)
        elif any(k in clean_col for k in ['last name', 'lastname', 'surname']):
            col_map.setdefault('surname', idx)
        elif any(k in clean_col for k in ['username', 'user name', 'login']):
            col_map.setdefault('username', idx)
        elif any(k in clean_col for k in ['email', 'mail', 'email id', 'email address']):
            col_map.setdefault('email', idx)
        elif any(k in clean_col for k in ['role', 'designation', 'user role', 'access']):
            col_map.setdefault('role', idx)
        elif any(k in clean_col for k in ['password', 'pass', 'temp password', 'initial password']):
            col_map.setdefault('password', idx)

    if 'email' not in col_map and 'username' not in col_map and 'name' not in col_map:
        return False, "Could not detect required columns (Name, Email, or Username) in the file header.", {}

    db = get_db()
    existing_users = list(db.users.find({}, {"email": 1, "username": 1}))
    existing_emails = {u.get("email", "").strip().lower() for u in existing_users if u.get("email")}
    existing_usernames = {u.get("username", "").strip().lower() for u in existing_users if u.get("username")}

    batch_emails = set()
    batch_usernames = set()
    valid_docs = []
    requested_roles = []
    errors = []
    total_processed = 0

    valid_roles = {"admin", "inventory_manager", "staff"}

    for row_idx, row in enumerate(rows[1:], start=2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        total_processed += 1

        def get_val(key):
            idx = col_map.get(key)
            if idx is not None and idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
            return ""

        raw_name = get_val('name')
        raw_surname = get_val('surname')
        raw_username = get_val('username')
        raw_email = get_val('email').lower()
        raw_role = get_val('role').lower().replace(" ", "_")
        raw_password = get_val('password')

        # 1. Validate Email
        if not raw_email or "@" not in raw_email or "." not in raw_email:
            errors.append(f"Row {row_idx}: Invalid or missing email address ('{raw_email}').")
            continue

        if raw_email in existing_emails or raw_email in batch_emails:
            errors.append(f"Row {row_idx}: Email '{raw_email}' is already registered or duplicated in file.")
            continue

        # 2. Name
        full_name = f"{raw_name} {raw_surname}".strip() if raw_surname else raw_name
        if not full_name:
            full_name = raw_email.split("@")[0].replace(".", " ").title()

        # 3. Username resolution
        username_candidate = raw_username
        if not username_candidate:
            base_user = "".join(c for c in (raw_name or raw_email.split("@")[0]) if c.isalnum()).lower()
            if not base_user:
                base_user = "staff"
            username_candidate = f"{base_user}{random.randint(10, 99)}"

        # Ensure uniqueness
        base_clean = username_candidate.lower()
        suffix = 1
        final_username = username_candidate
        while final_username.lower() in existing_usernames or final_username.lower() in batch_usernames:
            final_username = f"{username_candidate}{suffix}"
            suffix += 1

        # 4. Role normalization: imported staff are always created as "staff";
        # elevated roles from the file become pending role requests for admin approval.
        assigned_role = "staff"
        requested_role = None
        if raw_role in valid_roles:
            if raw_role != "staff":
                requested_role = raw_role
        elif "admin" in raw_role:
            requested_role = "admin"
        elif "manager" in raw_role or "inventory" in raw_role:
            requested_role = "inventory_manager"

        # 5. Password
        password_to_use = raw_password if (raw_password and len(raw_password) >= 6) else default_password
        if len(password_to_use) < 6:
            password_to_use = "Staff@123"

        now = datetime.now(timezone.utc)
        user_doc = {
            "username": final_username,
            "name": full_name,
            "email": raw_email,
            "password_hash": generate_password_hash(password_to_use),
            "role": assigned_role,
            "is_active": False,
            "last_active_at": now,
            "created_at": now,
            "updated_at": now
        }

        valid_docs.append(user_doc)
        requested_roles.append(requested_role)
        batch_emails.add(raw_email)
        batch_usernames.add(final_username.lower())

    if not valid_docs:
        err_detail = "; ".join(errors[:5]) if errors else "No valid user records found in file."
        return False, f"Import failed: {err_detail}", {"total_rows": total_processed, "imported_count": 0, "errors": errors}

    try:
        result = db.users.insert_many(valid_docs)
        inserted_ids = result.inserted_ids
        inserted_count = len(inserted_ids)

        role_request_count = 0
        role_request_errors = []
        for doc, requested_role, user_id in zip(valid_docs, requested_roles, inserted_ids):
            if not requested_role:
                continue
            role_request_doc = {
                "user_id": str(user_id),
                "username": doc["username"],
                "email": doc["email"],
                "current_role": "staff",
                "requested_role": requested_role,
                "reason": f"Role requested during bulk staff import by {imported_by}.",
                "status": "PENDING",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            db.role_requests.insert_one(role_request_doc)
            role_request_count += 1

        from inventory_app.services.audit_service import log_audit
        log_audit("bulk_staff_imported", imported_by, details={
            "imported_count": inserted_count,
            "role_request_count": role_request_count,
            "skipped_count": len(errors),
            "total_rows": total_processed
        })

        summary = {
            "total_rows": total_processed,
            "imported_count": inserted_count,
            "role_request_count": role_request_count,
            "skipped_count": len(errors),
            "errors": errors,
            "role_request_errors": role_request_errors,
            "imported_users": [{"username": d["username"], "email": d["email"], "role": d["role"], "requested_role": r} for d, r in zip(valid_docs, requested_roles)]
        }
        msg = f"Successfully imported {inserted_count} staff member(s)."
        msg += " Imported staff are created as inactive by default and must be activated by an Administrator."
        if role_request_count:
            msg += f" {role_request_count} role request(s) sent to the Administrator for approval."
        if errors:
            msg += f" {len(errors)} row(s) were skipped due to validation issues."

        return True, msg, summary
    except Exception as e:
        return False, f"Database insertion failed: {str(e)}", {"total_rows": total_processed, "imported_count": 0, "errors": [str(e)]}


def generate_staff_template(file_format: str = "xlsx") -> tuple[io.BytesIO, str, str]:
    """
    Generates a pre-formatted sample Excel/CSV template for bulk staff/employee import.
    Returns (BytesIO_stream, filename, mimetype).
    """
    import io
    if file_format == "csv":
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Surname", "Username", "Email", "Role", "Password"])
        writer.writerow(["Rahul", "Sharma", "rahul.sharma", "rahul.sharma@example.com", "staff", "Staff@123"])
        writer.writerow(["Priya", "Patel", "priya.patel", "priya.patel@example.com", "inventory_manager", "Manager@123"])
        writer.writerow(["Amit", "Verma", "amit.verma", "amit.verma@example.com", "staff", "Staff@123"])
        writer.writerow(["Neha", "Gupta", "neha.gupta", "neha.gupta@example.com", "admin", "Admin@123"])
        
        mem = io.BytesIO(output.getvalue().encode('utf-8'))
        mem.seek(0)
        return mem, "StockSetu_Staff_Import_Template.csv", "text/csv"
    # Default Excel (.xlsx)
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Staff Import Template"

    # Headers
    headers = ["Name", "Surname", "Username", "Email", "Role", "Password"]
    ws.append(headers)

    # Sample rows
    samples = [
        ["Rahul", "Sharma", "rahul.sharma", "rahul.sharma@company.com", "staff", "Staff@123"],
        ["Priya", "Patel", "priya.patel", "priya.patel@company.com", "inventory_manager", "Manager@123"],
        ["Amit", "Verma", "amit.verma", "amit.verma@company.com", "staff", "Staff@123"],
        ["Neha", "Gupta", "neha.gupta", "neha.gupta@company.com", "admin", "Admin@123"],
    ]
    for row in samples:
        ws.append(row)

    # Style Header
    header_fill = PatternFill(start_color="0B2545", end_color="0B2545", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Column widths
    col_widths = [18, 18, 20, 32, 22, 18]
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # Add instructions block below
    ws.append([])
    ws.append(["Instructions & Notes:"])
    ws.append(["1. Name and Email are required fields."])
    ws.append(["2. Username is optional. If left blank, it will be automatically generated."])
    ws.append(["3. Role must be one of: 'staff', 'inventory_manager', or 'admin' (defaults to 'staff')."])
    ws.append(["4. All imported users are created as 'staff'. Elevated roles ('inventory_manager'/'admin') are sent to the Administrator as role requests for approval."])
    ws.append(["5. Imported users are created as inactive by default and must be activated by an Administrator before they can log in."])
    ws.append(["6. Password is optional. If left blank, it defaults to 'Staff@123'."])

    note_font = Font(name="Segoe UI", size=9, italic=True, color="64748B")
    for r in range(7, 12):
        cell = ws.cell(row=r, column=1)
        cell.font = note_font

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output, "StockSetu_Staff_Import_Template.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

