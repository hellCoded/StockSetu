from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from inventory_app.utils.validators import validate_user_registration
from inventory_app.utils.decorators import login_required, roles_required, csrf_protected

user_bp = Blueprint('users', __name__)

@user_bp.route('/users')
@login_required
@roles_required('admin')
def list_users():
    from inventory_app.services.auth_service import get_all_users, get_all_role_requests, get_user_stats
    from inventory_app.utils.pagination import Pagination
    search = request.args.get('q', '').strip()
    role = request.args.get('role', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    users, total_count = get_all_users(
        search=search,
        role=role,
        page=page,
        per_page=per_page,
        return_total=True
    )
    pagination = Pagination(page=page, per_page=per_page, total=total_count)
    role_requests = get_all_role_requests()
    user_stats = get_user_stats()

    return render_template(
        'users/list.html',
        users=users,
        pagination=pagination,
        role_requests=role_requests,
        user_stats=user_stats,
        current_search=search,
        current_role=role
    )

@user_bp.route('/users/add', methods=['POST'])
@login_required
@roles_required('admin')
@csrf_protected
def add_user():
    from inventory_app.services.auth_service import register_user
    name = request.form.get('name', '').strip()
    surname = request.form.get('surname', '').strip()
    employee_id = request.form.get('employee_id', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    role = request.form.get('role', 'staff')

    data = {
        'name': name,
        'surname': surname,
        'employee_id': employee_id,
        'username': employee_id,
        'phone': phone,
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
        employee_id=data['employee_id'],
        username=data['employee_id'],
        email=data['email'],
        password=data['password'],
        role=data['role'],
        name=data['name'],
        surname=data['surname'],
        phone=data['phone']
    )
    
    if success:
        session['registered_user'] = {
            'name': f"{data['name']} {data['surname']}".strip() if data.get('surname') else data['name'],
            'employee_id': user.get('employee_id', ''),
            'username': user.get('employee_id', ''),
            'email': user['email'],
            'password': data['password']
        }
        flash(f"User '{user.get('employee_id')}' registered successfully!", "success")
    else:
        flash(msg, "danger")
        
    return redirect(url_for('users.list_users'))

@user_bp.route('/users/<user_id>/role', methods=['POST'])
@login_required
@roles_required('admin')
@csrf_protected
def change_role(user_id):
    from inventory_app.services.auth_service import update_user_role
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
    from inventory_app.services.auth_service import toggle_user_active
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
    from inventory_app.services.auth_service import get_user_by_id, create_role_request
    user_id = session.get('user_id')
    user = get_user_by_id(user_id)
    if not user:
        flash("Invalid user session.", "danger")
        return redirect(url_for('auth.login'))
        
    emp_id = user.get('employee_id') or user.get('username', '')
    email = user.get('email', '')
    reason = request.form.get('reason', '')
    requested_role = request.form.get('requested_role', 'inventory_manager')
    
    success, msg = create_role_request(user_id, employee_id=emp_id, email=email, requested_role=requested_role, reason=reason)
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
    from inventory_app.services.auth_service import process_role_request
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
    from inventory_app.services.auth_service import cancel_role_request
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
    from inventory_app.services.auth_service import get_user_by_id, get_user_pending_role_request, get_user_role_requests, update_user_profile_info, change_password
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


@user_bp.route('/users/bulk-import', methods=['POST'])
@login_required
@roles_required('admin')
@csrf_protected
def bulk_import_users():
    from inventory_app.services.auth_service import import_staff_bulk
    file = request.files.get('staff_file')
    default_pw = request.form.get('default_password', 'Staff@123').strip() or 'Staff@123'
    current_admin = session.get('username', 'admin')

    success, msg, details = import_staff_bulk(file, default_password=default_pw, imported_by=current_admin)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")
        
    return redirect(url_for('users.list_users'))


@user_bp.route('/users/template', methods=['GET'])
@login_required
@roles_required('admin')
def download_staff_template():
    from inventory_app.services.auth_service import generate_staff_template
    file_format = request.args.get('format', 'xlsx').lower()
    mem, filename, mimetype = generate_staff_template(file_format=file_format)
    return send_file(
        mem,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype
    )

