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
