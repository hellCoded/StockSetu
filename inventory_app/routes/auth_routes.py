import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from inventory_app.utils.decorators import login_required, csrf_protected
from inventory_app.utils.validators import validate_user_registration
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone

auth_bp = Blueprint('auth', __name__)

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

@auth_bp.route('/reset-admin')
def reset_admin():
    """One-time admin password reset. Access: /reset-admin?key=your-secret"""
    secret = request.args.get('key', '')
    expected = current_app.config.get('SECRET_KEY', '')
    if not secret or secret != expected:
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
        return "Admin password reset to: Admin@123456. You can now login."
    return "Admin user not found.", 404
