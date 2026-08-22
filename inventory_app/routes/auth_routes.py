import secrets
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from inventory_app.utils.decorators import login_required, csrf_protected
from inventory_app.utils.validators import validate_user_registration
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone

auth_bp = Blueprint('auth', __name__)

# Rate limit state for reset-admin: {ip: [timestamps]}
_RESET_ADMIN_RATE_LIMIT_STATE = {}
_RESET_ADMIN_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
_RESET_ADMIN_RATE_LIMIT_MAX = 1        # max attempts per window
_RESET_ADMIN_RATE_LIMIT_MAX_IPS = 100  # max tracked IPs to prevent OOM

# Rate limit state for login: {ip:identifier: [timestamps]} (failed attempts only)
_LOGIN_RATE_LIMIT_STATE = {}
_LOGIN_RATE_LIMIT_WINDOW = 60          # 1 minute in seconds
_LOGIN_RATE_LIMIT_MAX = 5              # max failed attempts per window
_LOGIN_RATE_LIMIT_MAX_KEYS = 500       # max tracked keys to prevent OOM


@auth_bp.errorhandler(429)
def _rate_limit_exceeded(e):
    """Handle rate limit exceeded with a proper response."""
    from flask import jsonify, request
    if request.is_json:
        return jsonify({"error": "Rate limit exceeded. Too many failed login attempts."}), 429
    from flask import render_template
    return render_template('auth/login.html', 
                           error="Too many failed login attempts. Please wait a minute before trying again."), 429


def _check_reset_admin_rate_limit():
    """Simple in-memory sliding-window rate limiter for reset-admin POST route."""
    from flask import request as req, abort, current_app
    # Only rate limit the reset-admin endpoint
    if req.method != 'POST' or not req.path.endswith('/reset-admin'):
        return
    # Skip rate limiting in testing mode
    if current_app.config.get('TESTING'):
        return
    ip = req.remote_addr or 'unknown'
    now = time.time()
    window_start = now - _RESET_ADMIN_RATE_LIMIT_WINDOW

    # Evict stale entries and cap dict size to prevent OOM
    if len(_RESET_ADMIN_RATE_LIMIT_STATE) > _RESET_ADMIN_RATE_LIMIT_MAX_IPS:
        stale_keys = [k for k, v in _RESET_ADMIN_RATE_LIMIT_STATE.items()
                      if not v or v[-1] < window_start]
        for k in stale_keys[:len(stale_keys) // 2]:
            _RESET_ADMIN_RATE_LIMIT_STATE.pop(k, None)

    hits = _RESET_ADMIN_RATE_LIMIT_STATE.get(ip, [])
    hits = [t for t in hits if t > window_start]
    if len(hits) >= _RESET_ADMIN_RATE_LIMIT_MAX:
        abort(429)
    hits.append(now)
    _RESET_ADMIN_RATE_LIMIT_STATE[ip] = hits


@auth_bp.before_request
def _reset_admin_rate_limit():
    _check_reset_admin_rate_limit()


def _check_login_rate_limit():
    """Simple in-memory sliding-window rate limiter for failed login attempts.
    
    Tracks failed attempts by composite key (IP:identifier) to prevent
    credential stuffing across different accounts from the same IP.
    Only failed attempts are counted; successful logins do not increment.
    """
    from flask import request as req, abort, current_app
    if req.method != 'POST' or not req.path.endswith('/login'):
        return
    # Skip rate limiting in testing mode unless explicitly enabled
    if current_app.config.get('TESTING') and not current_app.config.get('RATE_LIMIT_ENABLED'):
        return
    if req.form.get('identifier') is None:
        return
    
    ip = req.remote_addr or 'unknown'
    identifier = req.form.get('identifier', '').strip().lower()
    if not identifier:
        return
    
    # Composite key: IP + identifier (prevents credential stuffing across accounts)
    key = f"{ip}:{identifier}"
    now = time.time()
    window_start = now - _LOGIN_RATE_LIMIT_WINDOW

    # Evict stale entries and cap dict size to prevent OOM
    if len(_LOGIN_RATE_LIMIT_STATE) > _LOGIN_RATE_LIMIT_MAX_KEYS:
        stale_keys = [k for k, v in _LOGIN_RATE_LIMIT_STATE.items()
                      if not v or v[-1] < window_start]
        for k in stale_keys[:len(stale_keys) // 2]:
            _LOGIN_RATE_LIMIT_STATE.pop(k, None)

    hits = _LOGIN_RATE_LIMIT_STATE.get(key, [])
    hits = [t for t in hits if t > window_start]
    if len(hits) >= _LOGIN_RATE_LIMIT_MAX:
        abort(429)
    # Note: We only add the hit on FAILED login. The actual increment happens
    # in the login() function after authentication fails.
    # Store the window_start for cleanup reference
    _LOGIN_RATE_LIMIT_STATE[key] = hits


@auth_bp.before_request
def _login_rate_limit():
    _check_login_rate_limit()

@auth_bp.route('/login', methods=['GET', 'POST'])
@csrf_protected
def login():
    from inventory_app.services.auth_service import authenticate_user
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
        
    prefilled_identifier = ""
    if 'registered_user' in session:
        prefilled_identifier = session['registered_user'].get('employee_id', '')
        
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        
        success, msg, user = authenticate_user(identifier, password)
        if success:
            # Check if user needs to change password on first login
            if user.get('force_password_change'):
                # Store user_id in session for password change flow
                session['force_password_change_user_id'] = user['_id']
                flash("You must change your temporary password before continuing.", "warning")
                return redirect(url_for('users.profile', forced_password_change=True))
            
            # Clear any failed login rate limit hits on successful login
            if current_app.config.get('RATE_LIMIT_ENABLED'):
                ip = request.remote_addr or 'unknown'
                key = f"{ip}:{identifier.strip().lower()}"
                if key in _LOGIN_RATE_LIMIT_STATE:
                    _LOGIN_RATE_LIMIT_STATE.pop(key, None)
            # Generate a new session token and save it to DB — this invalidates
            # any previous session for the same user (single-session enforcement).
            session_token = secrets.token_hex(32)
            from inventory_app.database import get_db
            from bson import ObjectId
            get_db().users.update_one(
                {"_id": ObjectId(user['_id'])},
                {"$set": {"session_token": session_token, "updated_at": datetime.now(timezone.utc)}}
            )

            session.permanent = True
            now_ts = datetime.now(timezone.utc).timestamp()
            emp_id = user.get('employee_id', '')
            user_name = user.get('name', '')
            session['user_id'] = user['_id']
            session['employee_id'] = emp_id
            session['name'] = user_name
            session['email'] = user['email']
            session['role'] = user['role']
            session['session_token'] = session_token
            session['last_active_at'] = now_ts
            session['last_db_active_sync'] = now_ts
            flash(f"Welcome back, {user_name or emp_id}!", "success")
            
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('dashboard.index'))
        else:
            # Record failed login attempt for rate limiting
            if current_app.config.get('RATE_LIMIT_ENABLED'):
                ip = request.remote_addr or 'unknown'
                key = f"{ip}:{identifier.strip().lower()}"
                now = time.time()
                window_start = now - _LOGIN_RATE_LIMIT_WINDOW
                hits = _LOGIN_RATE_LIMIT_STATE.get(key, [])
                hits = [t for t in hits if t > window_start]
                hits.append(now)
                _LOGIN_RATE_LIMIT_STATE[key] = hits
            
            if "register" in msg.lower():
                flash(msg, "warning")
                return redirect(url_for('auth.register'))
            flash(msg, "danger")
            
    return render_template('auth/login.html', prefilled_identifier=prefilled_identifier)

@auth_bp.route('/register', methods=['GET', 'POST'])
@csrf_protected
def register():
    from inventory_app.services.auth_service import register_user
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', ''),
            'surname': request.form.get('surname', ''),
            'employee_id': request.form.get('employee_id', ''),
            'email': request.form.get('email', ''),
            'password': request.form.get('password', ''),
            'confirm_password': request.form.get('confirm_password', '')
        }
        
        is_valid, err_msg = validate_user_registration(data)
        if not is_valid:
            flash(err_msg, "danger")
            return render_template('auth/register.html', form_data=data)
            
        success, msg, user = register_user(
            employee_id=data['employee_id'],
            email=data['email'],
            password=data['password'],
            role='staff',
            name=data['name'],
            surname=data['surname']
        )
        
        if success:
            session['registered_user'] = {
                'name': f"{data['name']} {data['surname']}".strip() if data.get('surname') else data['name'],
                'employee_id': user.get('employee_id', ''),
                'email': user['email'],
            }
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash(msg, "danger")
            return render_template('auth/register.html', form_data=data)
            
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    # Clear session_token from DB so it can't be reused
    user_id = session.get('user_id')
    session_token = session.get('session_token')
    if user_id and session_token:
        try:
            from inventory_app.database import get_db
            from bson import ObjectId
            get_db().users.update_one(
                {"_id": ObjectId(user_id), "session_token": session_token},
                {"$unset": {"session_token": ""}}
            )
        except Exception:
            pass
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset-admin', methods=['GET'])
def reset_admin_get():
    """GET method not allowed for reset-admin endpoint."""
    return "Method Not Allowed", 405


@auth_bp.route('/reset-admin', methods=['POST'])
@csrf_protected
def reset_admin():
    """One-time admin password reset. POST only with CSRF protection.
    
    Disabled in production via DISABLE_RESET_ADMIN environment variable.
    Rate limited to 1 attempt per hour per IP.
    """
    # Production disable mechanism
    if current_app.config.get('DISABLE_RESET_ADMIN', '').lower() in ('true', '1', 't', 'yes'):
        return "Endpoint disabled in production", 404

    secret = request.form.get('key', '')
    expected = current_app.config.get('SECRET_KEY', '')
    
    # Constant-time comparison to prevent timing attacks
    if not secret or not expected or not secrets.compare_digest(secret, expected):
        return "Unauthorized", 403
    
    from inventory_app.database import get_db
    db = get_db()
    now = datetime.now(timezone.utc)
    new_hash = generate_password_hash("Admin@123456")
    result = db.users.update_one(
        {"$or": [{"role": "admin"}, {"employee_id": "EMP-0001"}]},
        {"$set": {"password_hash": new_hash, "updated_at": now},
         "$unset": {"session_token": ""}}
    )
    if result.matched_count:
        return "Admin password reset to default. You can now login."
    return "Admin user not found.", 404
