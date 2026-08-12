from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from inventory_app.services.auth_service import (
    get_all_users, update_user_role, toggle_user_active, change_password, get_user_by_id, register_user,
    create_role_request, get_user_pending_role_request, get_all_pending_role_requests, process_role_request,
    update_user_profile_info, cancel_role_request, get_all_role_requests, get_user_role_requests
)
from inventory_app.utils.validators import validate_user_registration
from inventory_app.utils.decorators import login_required, roles_required, csrf_protected

user_bp = Blueprint('users', __name__)

@user_bp.route('/users')
@login_required
@roles_required('admin')
def list_users():
    users = get_all_users()
    role_requests = get_all_role_requests()
    return render_template('users/list.html', users=users, role_requests=role_requests)

@user_bp.route('/users/add', methods=['POST'])
@login_required
@roles_required('admin')
@csrf_protected
def add_user():
    name = request.form.get('name', '').strip()
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    role = request.form.get('role', 'staff')
    
    if not username and name:
        import random
        clean_base = ''.join(e for e in name if e.isalnum()).lower()
        username = f"{clean_base}{random.randint(100000, 999999)}"

    data = {
        'name': name,
        'username': username,
        'email': email,
        'password': password,
        'confirm_password': confirm_password,
        'role': role
    }
    
    is_valid, err_msg = validate_user_registration(data)
    if not is_valid:
        flash(err_msg, "danger")
        return redirect(url_for('users.list_users'))
        
    success, msg, user = register_user(
        username=data['username'],
        email=data['email'],
        password=data['password'],
        role=data['role'],
        name=data['name']
    )
    
    if success:
        session['registered_user'] = {
            'name': data['name'],
            'username': user['username'],
            'email': user['email'],
            'password': data['password']
        }
        flash(f"User '{user['username']}' registered successfully!", "success")
    else:
        flash(msg, "danger")
        
    return redirect(url_for('users.list_users'))

@user_bp.route('/users/<user_id>/role', methods=['POST'])
@login_required
@roles_required('admin')
@csrf_protected
def change_role(user_id):
    if user_id == session.get('user_id'):
        flash("You cannot modify your own Administrator role.", "warning")
        return redirect(url_for('users.list_users'))

    new_role = request.form.get('role', '')
    success, msg = update_user_role(user_id, new_role)
    
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")
        
    return redirect(url_for('users.list_users'))

@user_bp.route('/users/<user_id>/toggle-active', methods=['POST'])
@login_required
@roles_required('admin')
@csrf_protected
def toggle_active_user(user_id):
    # Prevent self-deactivation of current admin
    if user_id == session.get('user_id'):
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for('users.list_users'))
        
    success, msg, new_status = toggle_user_active(user_id)
    if success:
        flash(msg, "success" if new_status else "info")
    else:
        flash(msg, "danger")
        
    return redirect(url_for('users.list_users'))

@user_bp.route('/request-promotion', methods=['POST'])
@login_required
@csrf_protected
def request_promotion():
    user_id = session.get('user_id')
    user = get_user_by_id(user_id)
    if not user:
        flash("Invalid user session.", "danger")
        return redirect(url_for('auth.login'))
        
    username = user.get('username', '')
    email = user.get('email', '')
    reason = request.form.get('reason', '')
    requested_role = request.form.get('requested_role', 'inventory_manager')
    
    success, msg = create_role_request(user_id, username, email, requested_role=requested_role, reason=reason)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "warning")
    return redirect(url_for('users.profile'))

@user_bp.route('/users/requests/<request_id>/approve', methods=['POST'])
@login_required
@roles_required('admin')
@csrf_protected
def approve_promotion_request(request_id):
    return _process_role_request_action(request_id, action="approve", success_category="success")

@user_bp.route('/users/requests/<request_id>/reject', methods=['POST'])
@login_required
@roles_required('admin')
@csrf_protected
def reject_promotion_request(request_id):
    return _process_role_request_action(request_id, action="reject", success_category="info")


def _process_role_request_action(request_id: str, action: str, success_category: str):
    """Shared handler for approve/reject role request actions."""
    admin_username = session.get('username', 'System Admin')
    admin_comment = request.form.get('admin_comment', '')
    success, msg = process_role_request(request_id, action=action, processed_by=admin_username, admin_comment=admin_comment)
    if success:
        flash(msg, success_category)
    else:
        flash(msg, "danger")
    return redirect(url_for('users.list_users', open_inbox=1))


@user_bp.route('/requests/<request_id>/cancel', methods=['POST'])
@login_required
@csrf_protected
def cancel_promotion_request(request_id):
    user_id = session.get('user_id')
    success, msg = cancel_role_request(request_id, user_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")
    return redirect(url_for('users.profile'))

@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@csrf_protected
def profile():
    user_id = session.get('user_id')
    user = get_user_by_id(user_id)
    pending_request = get_user_pending_role_request(user_id)
    requests_history = get_user_role_requests(user_id)
    
    if request.method == 'POST':
        action_type = request.form.get('action_type', 'change_password')
        
        if action_type == 'update_profile':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            success, msg = update_user_profile_info(user_id, name, email)
            if success:
                session['name'] = name
                session['email'] = email
                flash(msg, "success")
                return redirect(url_for('users.profile'))
            else:
                flash(msg, "danger")
        else:
            old_pw = request.form.get('current_password', '')
            new_pw = request.form.get('password', request.form.get('new_password', ''))
            confirm_pw = request.form.get('confirm_password', '')
            
            if new_pw != confirm_pw:
                flash("New password and confirmation do not match.", "danger")
                return render_template('users/profile.html', user=user, pending_request=pending_request, requests_history=requests_history)
                
            success, msg = change_password(user_id, old_pw, new_pw)
            if success:
                flash(msg, "success")
                return redirect(url_for('users.profile'))
            else:
                flash(msg, "danger")
                
    return render_template('users/profile.html', user=user, pending_request=pending_request, requests_history=requests_history)
