from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from inventory_app.services.billing_service import create_bill, get_bill_by_id, get_bills
from inventory_app.services.product_service import search_products, get_distinct_categories
from inventory_app.utils.decorators import login_required, roles_required, csrf_protected

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/billing')
@login_required
@roles_required('admin', 'inventory_manager', 'staff')
def pos():
    """POS quick-billing screen: search products, build cart, create GST invoice."""
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    products = search_products(query=query, category=category, is_active=True, sort_by="product_name", sort_dir=1)
    categories = get_distinct_categories()
    return render_template(
        'billing/pos.html',
        products=products,
        categories=categories,
        current_query=query,
        current_category=category
    )

@billing_bp.route('/billing/create', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager', 'staff')
@csrf_protected
def create():
    """Handles POS bill submission."""
    customer_data = {
        'customer_name': request.form.get('customer_name', ''),
        'customer_phone': request.form.get('customer_phone', ''),
        'customer_gstin': request.form.get('customer_gstin', ''),
        'payment_method': request.form.get('payment_method', 'CASH')
    }

    items = []
    names = request.form.getlist('item_name[]')
    quantities = request.form.getlist('item_quantity[]')
    for name, qty in zip(names, quantities):
        if not name.strip():
            continue
        items.append({'product_name': name, 'quantity': qty})

    username = session.get('username', 'System')
    success, msg, bill = create_bill(customer_data, items, performed_by=username)

    if success:
        flash(msg, "success")
        return redirect(url_for('billing.view_bill', bill_id=bill['_id']))

    flash(msg, "danger")
    return redirect(url_for('billing.pos'))

@billing_bp.route('/billing/bills')
@login_required
def list_bills():
    search = request.args.get('q', '').strip()
    bills = get_bills(search=search, limit=100)
    return render_template('billing/bills.html', bills=bills, current_search=search)

@billing_bp.route('/billing/bills/<bill_id>')
@login_required
def view_bill(bill_id):
    bill = get_bill_by_id(bill_id)
    if not bill:
        flash("Bill not found.", "warning")
        return redirect(url_for('billing.list_bills'))
    format_type = request.args.get('format', 'standard')
    return render_template('billing/bill_detail.html', bill=bill, format_type=format_type)