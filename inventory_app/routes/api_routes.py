"""API endpoints for AJAX consumption — product search, employee lookup, cart persistence."""
from flask import Blueprint, jsonify, request, session
from inventory_app.utils.decorators import login_required, roles_required
from inventory_app.utils.validators import validate_cart_data

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/products/search')
@login_required
def api_product_search():
    """Lightweight product search for POS — returns JSON, supports lazy pagination."""
    from inventory_app.services.product_service import search_products
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    products, total = search_products(
        query=q, category=category, is_active=True,
        sort_by='product_name', sort_dir=1,
        page=page, per_page=per_page, return_total=True,
    )
    # Slim down the payload — POS only needs name, price, gst, stock, category, hsn
    items = []
    for p in products:
        items.append({
            'name': p.get('product_name', ''),
            'price': round(float(p.get('price', 0)), 2),
            'gst': float(p.get('gst_rate', 0) or 0),
            'stock': float(p.get('quantity', 0)),
            'unit': p.get('unit', ''),
            'category': p.get('category', ''),
            'hsn': p.get('hsn_code', ''),
        })
    return jsonify({'items': items, 'total': total, 'page': page, 'per_page': per_page})


@api_bp.route('/products/stock')
@login_required
def api_product_stock():
    """Real-time stock check for a single product — bypasses cache.
    Returns current quantity, stock status, and unit.
    """
    from inventory_app.services.product_service import get_product_by_name
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'ok': False, 'error': 'Product name required'}), 400
    product = get_product_by_name(name, bypass_cache=True)
    if not product:
        return jsonify({'ok': False, 'error': 'Product not found', 'name': name}), 404
    if not product.get('is_active', True):
        return jsonify({'ok': False, 'error': 'Product is inactive', 'name': name}), 400
    return jsonify({
        'ok': True,
        'name': product.get('product_name', ''),
        'stock': float(product.get('quantity', 0)),
        'unit': product.get('unit', ''),
        'status': product.get('status', 'OUT OF STOCK'),
        'price': round(float(product.get('price', 0)), 2),
        'gst': float(product.get('gst_rate', 0) or 0),
    })


@api_bp.route('/employees/list')
@login_required
def api_employee_list():
    """Lightweight employee list for smart search autocomplete."""
    from inventory_app.services.billing_service import get_active_employees_for_billing
    employees = get_active_employees_for_billing()
    # Slim payload
    items = [
        {
            'id': e.get('employee_id', ''),
            'name': e.get('name', ''),
            'phone': e.get('phone', ''),
            'role': e.get('role', ''),
        }
        for e in employees
    ]
    return jsonify({'employees': items})


@api_bp.route('/cart/save', methods=['POST'])
@login_required
def api_cart_save():
    """Persist cart state server-side so it survives page refresh / device switch."""
    from inventory_app.database import get_db
    data = request.get_json(silent=True) or {}
    
    # Validate cart data before saving
    is_valid, error_msg = validate_cart_data(data)
    if not is_valid:
        return jsonify({'ok': False, 'error': error_msg}), 400
    
    employee_id = session.get('employee_id', 'anon')
    db = get_db()
    db.pos_drafts.update_one(
        {'employee_id': employee_id},
        {'$set': {
            'employee_id': employee_id,
            'cart': data.get('cart', []),
            'customer': data.get('customer'),
            'discount_percent': data.get('discount_percent', '0'),
            'shipping_charge': data.get('shipping_charge', '0'),
            'packing_charge': data.get('packing_charge', '0'),
            'payment_method': data.get('payment_method', 'CASH'),
            'updated_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        }},
        upsert=True,
    )
    return jsonify({'ok': True})


@api_bp.route('/cart/load')
@login_required
def api_cart_load():
    """Load persisted cart state."""
    from inventory_app.database import get_db
    employee_id = session.get('employee_id', 'anon')
    db = get_db()
    draft = db.pos_drafts.find_one({'employee_id': employee_id})
    if not draft:
        return jsonify({'cart': []})
    return jsonify({
        'cart': draft.get('cart', []),
        'customer': draft.get('customer'),
        'discount_percent': draft.get('discount_percent', '0'),
        'shipping_charge': draft.get('shipping_charge', '0'),
        'packing_charge': draft.get('packing_charge', '0'),
        'payment_method': draft.get('payment_method', 'CASH'),
    })


@api_bp.route('/cart/clear', methods=['POST'])
@login_required
def api_cart_clear():
    """Clear persisted cart."""
    from inventory_app.database import get_db
    employee_id = session.get('employee_id', 'anon')
    db = get_db()
    db.pos_drafts.delete_one({'employee_id': employee_id})
    return jsonify({'ok': True})


@api_bp.route('/user/session-info')
@login_required
def api_user_session_info():
    """Lightweight endpoint for JS polling — queries DB directly for fresh role,
    then syncs back into session so subsequent server renders are also correct.
    Also enforces single-session: if another login overwrote the token, return 401."""
    from inventory_app.database import get_db
    from bson import ObjectId
    uid = session.get('user_id')
    try:
        db_user = get_db().users.find_one(
            {"_id": ObjectId(uid)},
            {"role": 1, "name": 1, "employee_id": 1, "is_active": 1, "session_token": 1},
        )
    except Exception:
        db_user = None

    if not db_user or not db_user.get('is_active', True):
        session.clear()
        return jsonify({'error': 'session_expired'}), 401

    # Single-session enforcement via polling: if DB token differs from cookie
    # token, this session has been superseded by a newer login.
    session_token = session.get('session_token')
    db_token = db_user.get('session_token')
    if session_token and db_token and db_token != session_token:
        session.clear()
        return jsonify({'error': 'session_expired', 'reason': 'logged_in_elsewhere'}), 401

    # Force-sync session from DB so next page load is also correct
    session['role'] = db_user.get('role', 'staff')
    session['name'] = db_user.get('name', '')
    session['employee_id'] = db_user.get('employee_id', '')

    return jsonify({
        'role': session['role'],
        'name': session['name'],
        'employee_id': session['employee_id'],
    })
