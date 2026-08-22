import re
import secrets
from flask import session

def normalize_product_name(raw_name: str) -> str:
    """
    Normalizes product name by stripping leading/trailing whitespace
    and collapsing multiple spaces into a single space.
    """
    if not raw_name:
        return ""
    # Strip whitespace and collapse redundant spaces
    cleaned = re.sub(r'\s+', ' ', raw_name.strip())
    return cleaned

def validate_product_data(data: dict) -> tuple[bool, str]:
    """
    Validates product fields.
    Returns (is_valid, error_message).
    """
    raw_name = data.get('product_name', '')
    product_name = normalize_product_name(raw_name)
    
    if not product_name:
        return False, "Product name is required."
    
    if len(product_name) > 255:
        return False, "Product name cannot exceed 255 characters."
    
    # Category, unit validation
    if not data.get('category') or not data.get('category').strip():
        return False, "Category is required."
    
    if not data.get('unit') or not data.get('unit').strip():
        return False, "Unit of measure is required."
    
    # Numeric validations
    try:
        quantity = float(data.get('quantity', 0))
        if quantity < 0:
            return False, "Quantity cannot be negative."
    except (ValueError, TypeError):
        return False, "Quantity must be a valid number."
        
    try:
        price = float(data.get('price', 0))
        if price < 0:
            return False, "Price cannot be negative."
    except (ValueError, TypeError):
        return False, "Price must be a valid number."
        
    try:
        gst_rate = float(data.get('gst_rate', 0))
        if gst_rate < 0 or gst_rate > 28:
            return False, "GST rate must be between 0% and 28%."
    except (ValueError, TypeError):
        return False, "GST rate must be a valid number."

    hsn_code = (data.get('hsn_code') or '').strip()
    if len(hsn_code) > 8:
        return False, "HSN code cannot exceed 8 characters."
    if hsn_code and not re.match(r'^[0-9A-Za-z]+$', hsn_code):
        return False, "HSN code can only contain letters and numbers."

    return True, ""

def generate_employee_id(name: str = "") -> str:
    """
    Generates a unique employee ID slug with random 4-digit number.
    Example: 'EMP-1042'
    """
    digits = f"{secrets.randbelow(9000) + 1000}"
    return f"EMP-{digits}"

def validate_user_registration(data: dict) -> tuple[bool, str]:
    """Validates user registration input and ensures name and employee_id are provided."""
    name = (data.get('name') or '').strip()
    surname = (data.get('surname') or '').strip()
    employee_id = (data.get('employee_id') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''
    
    if not name:
        return False, "Name is required."
        
    if not employee_id:
        data['employee_id'] = generate_employee_id(name)
        employee_id = data['employee_id']
    elif len(employee_id) < 3:
        return False, "Employee ID must be at least 3 characters long."
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', employee_id):
        return False, "Employee ID can only contain letters, numbers, underscores, and hyphens."
    
    data['employee_id'] = employee_id

    if not email or '@' not in email:
        return False, "A valid email address is required."
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    
    if confirm_password and password != confirm_password:
        return False, "Passwords do not match."
        
    return True, ""

def generate_csrf_token():
    """Generates a CSRF token for the active user session if not already present."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token(form_token: str) -> bool:
    """Verifies that the submitted CSRF token matches session token."""
    session_token = session.get('csrf_token')
    if not session_token or not form_token:
        return False
    return secrets.compare_digest(session_token, form_token)


def validate_cart_data(data: dict) -> tuple[bool, str]:
    """
    Validates cart data for /api/cart/save.
    Returns (is_valid, error_message).
    """
    # Check payload size (max ~100KB)
    try:
        import json
        payload_size = len(json.dumps(data))
        if payload_size > 100 * 1024:
            return False, "Payload too large (max 100KB)"
    except Exception:
        return False, "Invalid JSON payload"
    
    # Validate cart array
    cart = data.get('cart')
    if not isinstance(cart, list):
        return False, "cart must be an array"
    
    if len(cart) > 1000:
        return False, "Too many cart items (max 1000)"
    
    # Validate each cart item
    for idx, item in enumerate(cart):
        if not isinstance(item, dict):
            return False, f"Cart item {idx} must be an object"
        
        # Validate required fields
        name = item.get('name')
        if not isinstance(name, str) or not name.strip():
            return False, f"Cart item {idx}: name is required and must be a non-empty string"
        
        # Validate price
        price = item.get('price')
        if price is None:
            return False, f"Cart item {idx}: price is required"
        try:
            price_val = float(price)
            if price_val < 0:
                return False, f"Cart item {idx}: price cannot be negative"
        except (ValueError, TypeError):
            return False, f"Cart item {idx}: price must be a valid number"
        
        # Validate gst
        gst = item.get('gst')
        if gst is None:
            return False, f"Cart item {idx}: gst is required"
        try:
            gst_val = float(gst)
            if gst_val < 0 or gst_val > 28:
                return False, f"Cart item {idx}: gst must be between 0 and 28"
        except (ValueError, TypeError):
            return False, f"Cart item {idx}: gst must be a valid number"
        
        # Validate qty
        qty = item.get('qty')
        if qty is None:
            return False, f"Cart item {idx}: qty is required"
        try:
            qty_val = float(qty)
            if qty_val <= 0:
                return False, f"Cart item {idx}: qty must be positive"
            if qty_val > 10000:
                return False, f"Cart item {idx}: qty too large (max 10000)"
        except (ValueError, TypeError):
            return False, f"Cart item {idx}: qty must be a valid number"
        
        # Validate stock
        stock = item.get('stock')
        if stock is None:
            return False, f"Cart item {idx}: stock is required"
        try:
            stock_val = float(stock)
            if stock_val < 0:
                return False, f"Cart item {idx}: stock cannot be negative"
        except (ValueError, TypeError):
            return False, f"Cart item {idx}: stock must be a valid number"
        
        # Validate disc (discount)
        disc = item.get('disc')
        if disc is None:
            return False, f"Cart item {idx}: disc is required"
        try:
            disc_val = float(disc)
            if disc_val < 0 or disc_val > 100:
                return False, f"Cart item {idx}: disc must be between 0 and 100"
        except (ValueError, TypeError):
            return False, f"Cart item {idx}: disc must be a valid number"
        
        # Validate isFree
        is_free = item.get('isFree')
        if not isinstance(is_free, bool):
            return False, f"Cart item {idx}: isFree must be a boolean"
    
    # Validate customer data (optional)
    customer = data.get('customer')
    if customer is not None:
        if not isinstance(customer, dict):
            return False, "customer must be an object"
        if 'name' in customer and not isinstance(customer['name'], str):
            return False, "customer.name must be a string"
        if 'employee_id' in customer and not isinstance(customer['employee_id'], str):
            return False, "customer.employee_id must be a string"
        if 'role' in customer and not isinstance(customer['role'], str):
            return False, "customer.role must be a string"
        if 'phone' in customer and not isinstance(customer['phone'], str):
            return False, "customer.phone must be a string"
    
    # Validate discount_percent
    discount_percent = data.get('discount_percent')
    if discount_percent is not None:
        try:
            disc_val = float(discount_percent)
            if disc_val < 0 or disc_val > 100:
                return False, "discount_percent must be between 0 and 100"
        except (ValueError, TypeError):
            return False, "discount_percent must be a valid number"
    
    # Validate shipping_charge
    shipping_charge = data.get('shipping_charge')
    if shipping_charge is not None:
        try:
            ship_val = float(shipping_charge)
            if ship_val < 0:
                return False, "shipping_charge cannot be negative"
        except (ValueError, TypeError):
            return False, "shipping_charge must be a valid number"
    
    # Validate packing_charge
    packing_charge = data.get('packing_charge')
    if packing_charge is not None:
        try:
            pack_val = float(packing_charge)
            if pack_val < 0:
                return False, "packing_charge cannot be negative"
        except (ValueError, TypeError):
            return False, "packing_charge must be a valid number"
    
    # Validate payment_method
    payment_method = data.get('payment_method')
    if payment_method is not None:
        valid_methods = ['CASH', 'UPI', 'CARD', 'CREDIT', 'SALARY_DEDUCTION']
        if payment_method not in valid_methods:
            return False, f"payment_method must be one of: {', '.join(valid_methods)}"
    
    return True, ""
