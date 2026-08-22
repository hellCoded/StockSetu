"""Tests for /api/products/search."""
import json
import pytest


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