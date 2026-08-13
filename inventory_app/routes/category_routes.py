from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from inventory_app.services.category_service import get_all_categories, create_category, delete_category
from inventory_app.utils.decorators import login_required, roles_required, csrf_protected

category_bp = Blueprint('categories', __name__)

@category_bp.route('/categories', methods=['GET'])
@login_required
def list_categories():
    categories = get_all_categories()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
        return jsonify({"success": True, "categories": categories})
    return render_template('categories/index.html', categories=categories)

@category_bp.route('/categories/add', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager')
@csrf_protected
def add_category():
    name = request.form.get('name', '')
    description = request.form.get('description', '')
    username = session.get('username', 'Unknown')

    success, msg, cat = create_category(name, description, username)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('categories.list_categories'))

@category_bp.route('/categories/<category_id>/delete', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager')
@csrf_protected
def remove_category(category_id):
    username = session.get('username', 'Unknown')
    success, msg = delete_category(category_id, username)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('categories.list_categories'))
