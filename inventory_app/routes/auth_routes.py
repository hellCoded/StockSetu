from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from inventory_app.services.auth_service import register_user, authenticate_user, change_password
from inventory_app.utils.decorators import login_required, csrf_protected
from inventory_app.utils.validators import validate_user_registration

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@csrf_protected
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
        
    prefilled_identifier = ""
    if 'registered_user' in session:
        prefilled_identifier = session['registered_user'].get('username', '')
        
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        
        success, msg, user = authenticate_user(identifier, password)
        if success:
            session['user_id'] = user['_id']
            session['username'] = user['username']
            session['email'] = user['email']
            session['role'] = user['role']
            flash(f"Welcome back, {user['username']}!", "success")
            
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
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
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', ''),
            'username': request.form.get('username', ''),
            'email': request.form.get('email', ''),
            'password': request.form.get('password', ''),
            'confirm_password': request.form.get('confirm_password', '')
        }
        
        is_valid, err_msg = validate_user_registration(data)
        if not is_valid:
            flash(err_msg, "danger")
            return render_template('auth/register.html', form_data=data)
            
        success, msg, user = register_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            role='staff',
            name=data['name']
        )
        
        if success:
            session['registered_user'] = {
                'name': data['name'],
                'username': user['username'],
                'email': user['email'],
                'password': data['password']
            }
            flash("Registration successful! Account credentials generated below.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash(msg, "danger")
            return render_template('auth/register.html', form_data=data)
            
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))
