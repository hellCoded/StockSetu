from functools import wraps
from flask import session, redirect, url_for, flash, request, current_app
from inventory_app.utils.validators import validate_csrf_token

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    """
    Decorator enforcing role-based access control.
    Example: @roles_required('admin', 'inventory_manager')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('auth.login', next=request.url))

            # Fast path: the role already stored in the session grants access,
            # so avoid a DB round-trip on every privileged request. The DB is
            # still consulted when the session role is absent or insufficient.
            if session.get('role') in roles:
                return f(*args, **kwargs)

            from inventory_app.services.auth_service import get_user_by_id
            user = get_user_by_id(session['user_id'])
            if not user:
                session.clear()
                flash("User account not found.", "danger")
                return redirect(url_for('auth.login'))
                
            user_role = user.get('role', 'staff')
            session['role'] = user_role
            
            if user_role not in roles:
                flash("Forbidden: You do not have permission to perform this action.", "danger")
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def csrf_protected(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            if current_app.config.get('TESTING') and not current_app.config.get('WTF_CSRF_ENABLED', True):
                return f(*args, **kwargs)
                
            form_token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
            if not validate_csrf_token(form_token):
                flash("Your session has expired. Please try again.", "danger")
                return redirect(request.referrer or url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function
