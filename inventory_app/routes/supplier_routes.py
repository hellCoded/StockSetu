from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from inventory_app.services.supplier_service import get_all_suppliers, create_supplier, delete_supplier
from inventory_app.utils.decorators import login_required, roles_required, csrf_protected

supplier_bp = Blueprint('suppliers', __name__)

@supplier_bp.route('/suppliers', methods=['GET'])
@login_required
def list_suppliers():
    suppliers = get_all_suppliers()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
        return jsonify({"success": True, "suppliers": suppliers})
    return render_template('suppliers/index.html', suppliers=suppliers)

@supplier_bp.route('/suppliers/add', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager')
@csrf_protected
def add_supplier():
    code = request.form.get('code', '')
    name = request.form.get('name', '')
    contact_person = request.form.get('contact_person', '')
    phone = request.form.get('phone', '')
    email = request.form.get('email', '')
    username = session.get('username', 'Unknown')

    success, msg, sup = create_supplier(code, name, contact_person, phone, email, username)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('suppliers.list_suppliers'))

@supplier_bp.route('/suppliers/<supplier_id>/delete', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager')
@csrf_protected
def remove_supplier(supplier_id):
    username = session.get('username', 'Unknown')
    success, msg = delete_supplier(supplier_id, username)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('suppliers.list_suppliers'))
