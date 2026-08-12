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
        minimum_stock = float(data.get('minimum_stock', 0))
        if minimum_stock < 0:
            return False, "Minimum stock level cannot be negative."
    except (ValueError, TypeError):
        return False, "Minimum stock level must be a valid number."

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

def generate_username_from_name(name: str) -> str:
    """
    Generates a unique username combining name slug + random 6-digit number.
    Example: 'John Doe' -> 'johndoe749102'
    """
    if not name:
        base = "user"
    else:
        base = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
        if not base:
            base = "user"
    digits = f"{secrets.randbelow(900000) + 100000}"
    return f"{base}{digits}"

def validate_user_registration(data: dict) -> tuple[bool, str]:
    """Validates user registration input and ensures full name is provided."""
    name = (data.get('name') or '').strip()
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''
    
    if not name:
        return False, "Full Name is required."
        
    if not username:
        data['username'] = generate_username_from_name(name)
        username = data['username']
    elif len(username) < 3:
        return False, "Username must be at least 3 characters long."
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens."
    
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
