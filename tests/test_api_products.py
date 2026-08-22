"""Tests for /api/products/search."""
import json
import pytest
from datetime import datetime, timezone


def test_api_products_search_requires_auth(client):
    """Unauthenticated request should be rejected."""
    response = client.get('/api/products/search')
    assert response.status_code == 302  # Redirect to login


def test_api_products_search_empty_query(admin_client, mock_mongo):
    """Empty query returns all active products."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_many([
        {
            "product_name": "Test Product A",
            "product_name_lower": "test product a",
            "category": "Electronics",
            "quantity": 10,
            "price": 100.0,
            "gst_rate": 18,
            "unit": "PCS",
            "hsn_code": "8471",
            "location": "Warehouse 1",
            "is_active": True,
        },
        {
            "product_name": "Test Product B",
            "product_name_lower": "test product b",
            "category": "Accessories",
            "quantity": 5,
            "price": 50.0,
            "gst_rate": 12,
            "unit": "PCS",
            "hsn_code": "8473",
            "location": "Warehouse 1",
            "is_active": True,
        },
    ])
    
    response = admin_client.get('/api/products/search')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'items' in data
    assert 'total' in data
    assert data['total'] == 2
    assert len(data['items']) == 2


def test_api_products_search_with_query(admin_client, mock_mongo):
    """Search by product name."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_many([
        {
            "product_name": "Apple iPhone 15",
            "product_name_lower": "apple iphone 15",
            "category": "Electronics",
            "quantity": 10,
            "price": 100.0,
            "gst_rate": 18,
            "unit": "PCS",
            "hsn_code": "8471",
            "location": "Warehouse 1",
            "is_active": True,
        },
        {
            "product_name": "Samsung Galaxy S24",
            "product_name_lower": "samsung galaxy s24",
            "category": "Electronics",
            "quantity": 5,
            "price": 50.0,
            "gst_rate": 18,
            "unit": "PCS",
            "hsn_code": "8471",
            "location": "Warehouse 1",
            "is_active": True,
        },
    ])
    
    response = admin_client.get('/api/products/search?q=apple')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['total'] == 1
    assert data['items'][0]['name'] == 'Apple iPhone 15'


def test_api_products_search_with_category(admin_client, mock_mongo):
    """Filter by category."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_many([
        {
            "product_name": "Product A",
            "product_name_lower": "product a",
            "category": "Electronics",
            "quantity": 10,
            "price": 100.0,
            "gst_rate": 18,
            "unit": "PCS",
            "hsn_code": "8471",
            "location": "Warehouse 1",
            "is_active": True,
        },
        {
            "product_name": "Product B",
            "product_name_lower": "product b",
            "category": "Accessories",
            "quantity": 5,
            "price": 50.0,
            "gst_rate": 12,
            "unit": "PCS",
            "hsn_code": "8473",
            "location": "Warehouse 1",
            "is_active": True,
        },
    ])
    
    response = admin_client.get('/api/products/search?category=Electronics')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['total'] == 1
    assert data['items'][0]['category'] == 'Electronics'


def test_api_products_search_inactive_excluded(admin_client, mock_mongo):
    """Inactive products should not be returned."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_many([
        {
            "product_name": "Active Product",
            "product_name_lower": "active product",
            "category": "Electronics",
            "quantity": 10,
            "price": 100.0,
            "gst_rate": 18,
            "unit": "PCS",
            "hsn_code": "8471",
            "location": "Warehouse 1",
            "is_active": True,
        },
        {
            "product_name": "Inactive Product",
            "product_name_lower": "inactive product",
            "category": "Electronics",
            "quantity": 5,
            "price": 50.0,
            "gst_rate": 18,
            "unit": "PCS",
            "hsn_code": "8471",
            "location": "Warehouse 1",
            "is_active": False,
        },
    ])
    
    response = admin_client.get('/api/products/search')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['total'] == 1
    assert data['items'][0]['name'] == 'Active Product'


def test_api_products_search_pagination(admin_client, mock_mongo):
    """Test pagination parameters."""
    db = mock_mongo['inventory_test_db']
    products = [
        {
            "product_name": f"Product {i}",
            "product_name_lower": f"product {i}",
            "category": "Electronics",
            "quantity": 10,
            "price": 100.0,
            "gst_rate": 18,
            "unit": "PCS",
            "hsn_code": "8471",
            "location": "Warehouse 1",
            "is_active": True,
        }
        for i in range(5)
    ]
    db.products.insert_many(products)
    
    # Page 1, 2 per page
    response = admin_client.get('/api/products/search?page=1&per_page=2')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['page'] == 1
    assert data['per_page'] == 2
    assert len(data['items']) == 2
    assert data['total'] == 5
    
    # Page 2
    response = admin_client.get('/api/products/search?page=2&per_page=2')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['page'] == 2
    assert len(data['items']) == 2


def test_api_products_search_no_results(admin_client, mock_mongo):
    """Query with no matches returns empty list."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        "product_name": "Product A",
        "product_name_lower": "product a",
        "category": "Electronics",
        "quantity": 10,
        "price": 100.0,
        "gst_rate": 18,
        "unit": "PCS",
        "hsn_code": "8471",
        "location": "Warehouse 1",
        "is_active": True,
    })
    
    response = admin_client.get('/api/products/search?q=nonexistent')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['total'] == 0
    assert data['items'] == []


def test_api_products_search_works_for_staff(staff_client, mock_mongo):
    """Staff role can access product search."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        "product_name": "Test Product",
        "product_name_lower": "test product",
        "category": "Electronics",
        "quantity": 10,
        "price": 100.0,
        "gst_rate": 18,
        "unit": "PCS",
        "hsn_code": "8471",
        "location": "Warehouse 1",
        "is_active": True,
    })
    
    response = staff_client.get('/api/products/search')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['total'] == 1


def test_api_products_search_works_for_manager(manager_client, mock_mongo):
    """Manager role can access product search."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        "product_name": "Test Product",
        "product_name_lower": "test product",
        "category": "Electronics",
        "quantity": 10,
        "price": 100.0,
        "gst_rate": 18,
        "unit": "PCS",
        "hsn_code": "8471",
        "location": "Warehouse 1",
        "is_active": True,
    })
    
    response = manager_client.get('/api/products/search')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['total'] == 1


# ──────────────────────────────────────────────────────────────────────
# Real-time Stock Check (/api/products/stock)
# ──────────────────────────────────────────────────────────────────────

def test_api_product_stock_requires_auth(client):
    """Unauthenticated request should be rejected."""
    response = client.get('/api/products/stock?name=Test')
    assert response.status_code == 302  # Redirect to login


def test_api_product_stock_missing_name(admin_client, mock_mongo):
    """Missing name parameter returns 400."""
    response = admin_client.get('/api/products/stock')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['ok'] is False
    assert 'Product name required' in data['error']


def test_api_product_stock_not_found(admin_client, mock_mongo):
    """Non-existent product returns 404."""
    response = admin_client.get('/api/products/stock?name=NonExistent')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['ok'] is False
    assert 'Product not found' in data['error']


def test_api_product_stock_inactive_product(admin_client, mock_mongo):
    """Inactive product returns 400."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        "product_name": "Inactive Product",
        "product_name_lower": "inactive product",
        "category": "Electronics",
        "quantity": 10,
        "price": 100.0,
        "gst_rate": 18,
        "unit": "PCS",
        "hsn_code": "8471",
        "location": "Warehouse 1",
        "is_active": False,
    })
    
    response = admin_client.get('/api/products/stock?name=Inactive Product')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['ok'] is False
    assert 'Product is inactive' in data['error']


def test_api_product_stock_valid_current_stock(admin_client, mock_mongo):
    """Valid product returns current stock and details."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        "product_name": "Stock Test Product",
        "product_name_lower": "stock test product",
        "category": "Electronics",
        "quantity": 42,
        "price": 123.45,
        "gst_rate": 18,
        "unit": "PCS",
        "hsn_code": "8471",
        "location": "Warehouse 1",
        "is_active": True,
    })
    
    response = admin_client.get('/api/products/stock?name=Stock Test Product')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True
    assert data['name'] == 'Stock Test Product'
    assert data['stock'] == 42.0
    assert data['unit'] == 'PCS'
    assert data['status'] == 'IN STOCK'
    assert data['price'] == 123.45
    assert data['gst'] == 18.0


def test_api_product_stock_insufficient_current_stock(admin_client, mock_mongo):
    """Product with low stock returns correct quantity."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        "product_name": "Low Stock Product",
        "product_name_lower": "low stock product",
        "category": "Electronics",
        "quantity": 2,
        "price": 50.0,
        "gst_rate": 12,
        "unit": "PCS",
        "hsn_code": "8471",
        "location": "Warehouse 1",
        "is_active": True,
    })
    
    response = admin_client.get('/api/products/stock?name=Low Stock Product')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True
    assert data['stock'] == 2.0
    assert data['status'] == 'LOW STOCK'


def test_api_product_stock_out_of_stock(admin_client, mock_mongo):
    """Product with zero stock returns OUT OF STOCK status."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        "product_name": "Out of Stock Product",
        "product_name_lower": "out of stock product",
        "category": "Electronics",
        "quantity": 0,
        "price": 100.0,
        "gst_rate": 18,
        "unit": "PCS",
        "hsn_code": "8471",
        "location": "Warehouse 1",
        "is_active": True,
    })
    
    response = admin_client.get('/api/products/stock?name=Out of Stock Product')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True
    assert data['stock'] == 0.0
    assert data['status'] == 'OUT OF STOCK'


def test_api_product_stock_concurrent_deduction_scenario(admin_client, mock_mongo):
    """Stock check reflects concurrent deduction (bypasses cache)."""
    db = mock_mongo['inventory_test_db']
    # Insert product with initial stock
    db.products.insert_one({
        "product_name": "Concurrent Product",
        "product_name_lower": "concurrent product",
        "category": "Electronics",
        "quantity": 10,
        "price": 100.0,
        "gst_rate": 18,
        "unit": "PCS",
        "hsn_code": "8471",
        "location": "Warehouse 1",
        "is_active": True,
    })
    
    # First check - should see 10
    response = admin_client.get('/api/products/stock?name=Concurrent Product')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['stock'] == 10.0
    
    # Simulate concurrent deduction (direct DB update, bypassing cache)
    db.products.update_one(
        {"product_name": "Concurrent Product"},
        {"$inc": {"quantity": -3}}
    )
    
    # Second check - should see 7 (bypasses cache)
    response = admin_client.get('/api/products/stock?name=Concurrent Product')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['stock'] == 7.0
    assert data['status'] == 'IN STOCK'


# ──────────────────────────────────────────────────────────────────────
# Customer Search (/api/customers/search)
# ──────────────────────────────────────────────────────────────────────

def test_api_customer_search_requires_auth(client):
    """Unauthenticated request should be rejected."""
    response = client.get('/api/customers/search?q=test')
    assert response.status_code == 302  # Redirect to login


def test_api_customer_search_missing_query(admin_client, mock_mongo):
    """Missing or too short query returns empty list."""
    # Too short query
    response = admin_client.get('/api/customers/search?q=a')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['customers'] == []
    
    # No query
    response = admin_client.get('/api/customers/search')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['customers'] == []


def test_api_customer_search_by_name(admin_client, mock_mongo):
    """Search customers by name from invoice history."""
    db = mock_mongo['inventory_test_db']
    # Create invoices with customer data
    now = datetime.now(timezone.utc)
    db.invoices.insert_many([
        {
            "bill_number": "INV/001",
            "customer_name": "John Smith",
            "customer_name_lower": "john smith",
            "customer_phone": "9876543210",
            "customer_gstin": "27ABCDE1234F1Z5",
            "grand_total": 1000.0,
            "created_at": now,
        },
        {
            "bill_number": "INV/002",
            "customer_name": "John Doe",
            "customer_name_lower": "john doe",
            "customer_phone": "9876543211",
            "customer_gstin": "",
            "grand_total": 2000.0,
            "created_at": now,
        },
        {
            "bill_number": "INV/003",
            "customer_name": "Jane Smith",
            "customer_name_lower": "jane smith",
            "customer_phone": "9876543212",
            "customer_gstin": "27ABCDE1234F1Z6",
            "grand_total": 1500.0,
            "created_at": now,
        },
    ])
    
    # Search by name "john" - should return both Johns
    response = admin_client.get('/api/customers/search?q=john')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['customers']) == 2
    names = {c['name'] for c in data['customers']}
    assert 'John Smith' in names
    assert 'John Doe' in names
    
    # Search by "smith" - should return both Smiths
    response = admin_client.get('/api/customers/search?q=smith')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['customers']) == 2
    names = {c['name'] for c in data['customers']}
    assert 'John Smith' in names
    assert 'Jane Smith' in names


def test_api_customer_search_by_phone(admin_client, mock_mongo):
    """Search customers by phone number."""
    db = mock_mongo['inventory_test_db']
    now = datetime.now(timezone.utc)
    db.invoices.insert_one({
        "bill_number": "INV/001",
        "customer_name": "Phone Customer",
        "customer_name_lower": "phone customer",
        "customer_phone": "9999988888",
        "customer_gstin": "",
        "grand_total": 1000.0,
        "created_at": now,
    })
    
    response = admin_client.get('/api/customers/search?q=9999988888')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['customers']) == 1
    assert data['customers'][0]['name'] == 'Phone Customer'
    assert data['customers'][0]['phone'] == '9999988888'


def test_api_customer_search_by_gstin(admin_client, mock_mongo):
    """Search customers by GSTIN."""
    db = mock_mongo['inventory_test_db']
    now = datetime.now(timezone.utc)
    db.invoices.insert_one({
        "bill_number": "INV/001",
        "customer_name": "GST Customer",
        "customer_name_lower": "gst customer",
        "customer_phone": "9876543210",
        "customer_gstin": "27ABCDE1234F1Z5",
        "grand_total": 1000.0,
        "created_at": now,
    })
    
    response = admin_client.get('/api/customers/search?q=27ABCDE1234F1Z5')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['customers']) == 1
    assert data['customers'][0]['name'] == 'GST Customer'
    assert data['customers'][0]['gstin'] == '27ABCDE1234F1Z5'


def test_api_customer_search_result_limit(admin_client, mock_mongo):
    """Results are limited to max 10 (or specified limit)."""
    db = mock_mongo['inventory_test_db']
    now = datetime.now(timezone.utc)
    # Create 15 customers with similar names
    for i in range(15):
        db.invoices.insert_one({
            "bill_number": f"INV/{i:03d}",
            "customer_name": f"Customer {i}",
            "customer_name_lower": f"customer {i}",
            "customer_phone": f"98765432{i:02d}",
            "customer_gstin": "",
            "grand_total": 1000.0,
            "created_at": now,
        })
    
    # Default limit (10)
    response = admin_client.get('/api/customers/search?q=customer')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['customers']) <= 10
    
    # Custom limit (5)
    response = admin_client.get('/api/customers/search?q=customer&limit=5')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['customers']) == 5


def test_api_customer_search_unauthorized(client):
    """Unauthenticated access is rejected."""
    response = client.get('/api/customers/search?q=test')
    assert response.status_code == 302  # Redirect to login