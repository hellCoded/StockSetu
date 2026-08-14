from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from inventory_app.utils.decorators import login_required, roles_required, csrf_protected

billing_bp = Blueprint('billing', __name__)

# Rate limit state: {ip: [timestamps]}
_rate_limit_state = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 60     # max requests per window
_RATE_LIMIT_MAX_IPS = 500  # max tracked IPs to prevent OOM


def _check_rate_limit():
    """Simple in-memory sliding-window rate limiter for POST routes."""
    import time
    from flask import request as req, abort
    if req.method != 'POST':
        return
    ip = req.remote_addr or 'unknown'
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Evict stale entries and cap dict size to prevent OOM
    if len(_rate_limit_state) > _RATE_LIMIT_MAX_IPS:
        stale_keys = [k for k, v in _rate_limit_state.items()
                      if not v or v[-1] < window_start]
        for k in stale_keys[:len(stale_keys) // 2]:
            _rate_limit_state.pop(k, None)

    hits = _rate_limit_state.get(ip, [])
    hits = [t for t in hits if t > window_start]
    if len(hits) >= RATE_LIMIT_MAX:
        abort(429)
    hits.append(now)
    _rate_limit_state[ip] = hits


@billing_bp.before_request
def _billing_rate_limit():
    _check_rate_limit()


def _limiter():
    """Returns the Flask-Limiter instance if available, else None."""
    return current_app.extensions.get('limiter')


@billing_bp.route('/billing')
@login_required
@roles_required('admin', 'inventory_manager', 'staff')
def pos():
    """POS quick-billing screen: search products, build cart, create GST invoice."""
    from inventory_app.services.product_service import search_products, get_distinct_categories
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
def create_bill():
    """Handles POS bill submission. Rate limited to 30 creates/min per user."""
    from inventory_app.services.billing_service import create_bill
    customer_data = {
        'customer_name': request.form.get('customer_name', ''),
        'customer_phone': request.form.get('customer_phone', ''),
        'customer_gstin': request.form.get('customer_gstin', ''),
        'payment_method': request.form.get('payment_method', 'CASH'),
        'discount_percent': request.form.get('discount_percent', '0'),
        'due_date': request.form.get('due_date', '') or None,
    }

    items = []
    names = request.form.getlist('item_name[]')
    quantities = request.form.getlist('item_quantity[]')
    discounts = request.form.getlist('item_discount[]')
    free_flags = request.form.getlist('item_free[]')
    for i, name in enumerate(names):
        if not name.strip():
            continue
        item = {
            'product_name': name,
            'quantity': quantities[i] if i < len(quantities) else '1',
        }
        if i < len(discounts) and discounts[i]:
            item['line_discount_percent'] = discounts[i]
        if i < len(free_flags) and free_flags[i] == '1':
            item['is_free'] = True
        items.append(item)

    charges = {
        'shipping_charge': request.form.get('shipping_charge', '0'),
        'packing_charge': request.form.get('packing_charge', '0'),
    }

    # Split payment support
    payment_splits = []
    split_methods = request.form.getlist('split_method[]')
    split_amounts = request.form.getlist('split_amount[]')
    split_refs = request.form.getlist('split_reference[]')
    for j in range(len(split_methods)):
        if j < len(split_amounts) and split_amounts[j]:
            payment_splits.append({
                'method': split_methods[j],
                'amount': split_amounts[j],
                'reference': split_refs[j] if j < len(split_refs) else '',
            })

    username = session.get('username', 'System')
    success, msg, bill = create_bill(
        customer_data, items, performed_by=username,
        charges=charges,
        payment_splits=payment_splits if payment_splits else None,
    )

    if success:
        flash(msg, "success")
        return redirect(url_for('billing.view_bill', bill_id=bill['_id']))

    flash(msg, "danger")
    return redirect(url_for('billing.pos'))


@billing_bp.route('/billing/bills')
@login_required
def list_bills():
    from inventory_app.services.billing_service import get_bills
    search = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    bills = get_bills(search=search, limit=50, payment_status=status)
    return render_template('billing/bills.html', bills=bills, current_search=search, current_status=status)


@billing_bp.route('/billing/bills/<bill_id>')
@login_required
def view_bill(bill_id):
    from inventory_app.services.billing_service import get_bill_by_id, get_bill_payments, get_bill_audit_history
    bill = get_bill_by_id(bill_id)
    if not bill:
        flash("Bill not found.", "warning")
        return redirect(url_for('billing.list_bills'))
    format_type = request.args.get('format', 'standard')
    payments = get_bill_payments(bill_id)
    audit_history = get_bill_audit_history(bill.get("bill_number", ""))
    return render_template(
        'billing/bill_detail.html',
        bill=bill,
        format_type=format_type,
        payments=payments,
        audit_history=audit_history,
    )


@billing_bp.route('/billing/bills/<bill_id>/refund', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager')
@csrf_protected
def refund_bill(bill_id):
    from inventory_app.services.billing_service import refund_bill
    reason = request.form.get('reason', 'Customer Refund')
    username = session.get('username', 'Unknown')
    success, msg = refund_bill(bill_id, reason, username)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")
    return redirect(url_for('billing.view_bill', bill_id=bill_id))


@billing_bp.route('/billing/bills/<bill_id>/refund-lines', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager')
@csrf_protected
def refund_lines(bill_id):
    """Refund specific line(s) of a bill."""
    from inventory_app.services.billing_service import refund_bill_lines
    line_indices = request.form.getlist('line_index[]')
    reason = request.form.get('reason', 'Line refund')
    username = session.get('username', 'Unknown')
    success, msg = refund_bill_lines(bill_id, line_indices, reason, username)
    flash(msg, "success" if success else "danger")
    return redirect(url_for('billing.view_bill', bill_id=bill_id))


@billing_bp.route('/billing/bills/<bill_id>/pay', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager', 'staff')
@csrf_protected
def record_payment(bill_id):
    """Record a payment against a bill."""
    from inventory_app.services.billing_service import record_bill_payment
    try:
        amount = float(request.form.get('amount', 0))
    except (ValueError, TypeError):
        amount = 0
    method = request.form.get('method', 'CASH')
    reference = request.form.get('reference', '')
    username = session.get('username', 'Unknown')
    success, msg = record_bill_payment(bill_id, amount, method, reference, username)
    flash(msg, "success" if success else "danger")
    return redirect(url_for('billing.view_bill', bill_id=bill_id))


@billing_bp.route('/billing/bills/<bill_id>/edit', methods=['POST'])
@login_required
@roles_required('admin', 'inventory_manager')
@csrf_protected
def edit_bill(bill_id):
    """Edit a bill's line items and charges."""
    from inventory_app.services.billing_service import edit_bill
    customer_data = {
        'customer_name': request.form.get('customer_name', ''),
        'customer_phone': request.form.get('customer_phone', ''),
        'customer_gstin': request.form.get('customer_gstin', ''),
        'payment_method': request.form.get('payment_method', 'CASH'),
        'discount_percent': request.form.get('discount_percent', '0'),
        'due_date': request.form.get('due_date', '') or None,
    }

    items = []
    names = request.form.getlist('item_name[]')
    quantities = request.form.getlist('item_quantity[]')
    discounts = request.form.getlist('item_discount[]')
    free_flags = request.form.getlist('item_free[]')
    for i, name in enumerate(names):
        if not name.strip():
            continue
        item = {
            'product_name': name,
            'quantity': quantities[i] if i < len(quantities) else '1',
        }
        if i < len(discounts) and discounts[i]:
            item['line_discount_percent'] = discounts[i]
        if i < len(free_flags) and free_flags[i] == '1':
            item['is_free'] = True
        items.append(item)

    charges = {
        'shipping_charge': request.form.get('shipping_charge', '0'),
        'packing_charge': request.form.get('packing_charge', '0'),
    }

    username = session.get('username', 'Unknown')
    success, msg, bill = edit_bill(bill_id, items, charges, customer_data, username)
    flash(msg, "success" if success else "danger")
    return redirect(url_for('billing.view_bill', bill_id=bill_id))


@billing_bp.route('/billing/reconciliation')
@login_required
@roles_required('admin')
def reconciliation():
    """Admin reconciliation report: flags anomalies across bills, stock, and audit."""
    from inventory_app.services.billing_service import get_reconciliation_report
    anomalies = get_reconciliation_report()
    return render_template('billing/reconciliation.html', anomalies=anomalies)
