"""Tests for /api/cart/load and /api/cart/clear."""
import json
import pytest


def test_api_cart_load_requires_auth(client):
    """Unauthenticated request should be rejected."""
    response = client.get('/api/cart/load')
    assert response.status_code == 302


def test_api_cart_load_empty_cart(admin_client):
    """Loading empty cart returns empty cart array."""
    response = admin_client.get('/api/cart/load')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['cart'] == []
    # When cart is empty, only 'cart' key is returned
    assert data.get('customer') is None
    assert data.get('discount_percent') is None
    assert data.get('payment_method') is None


def test_api_cart_load_after_save(admin_client):
    """Loading cart after saving returns saved data."""
    # Save a cart
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [
                {'name': 'Product A', 'price': 100.0, 'gst': 18, 'qty': 2, 'stock': 100, 'disc': 0, 'isFree': False}
            ],
            'customer': {'name': 'Test Customer', 'employee_id': 'EMP-001'},
            'discount_percent': '10',
            'shipping_charge': '50',
            'packing_charge': '20',
            'payment_method': 'CARD'
        }),
        content_type='application/json'
    )
    assert response.status_code == 200
    
    # Load the cart
    response = admin_client.get('/api/cart/load')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['cart']) == 1
    assert data['cart'][0]['name'] == 'Product A'
    assert data['customer']['name'] == 'Test Customer'
    assert data['discount_percent'] == '10'
    assert data['shipping_charge'] == '50'
    assert data['packing_charge'] == '20'
    assert data['payment_method'] == 'CARD'


def test_api_cart_load_different_users(admin_client, staff_client, mock_mongo):
    """Each user has their own cart."""
    db = mock_mongo['inventory_test_db']
    
    # Admin saves a cart
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Admin Product', 'price': 100.0, 'gst': 18, 'qty': 1, 'stock': 100, 'disc': 0, 'isFree': False}],
            'customer': {'name': 'Admin Customer', 'employee_id': 'ADM-001'},
            'discount_percent': '5',
            'shipping_charge': '10',
            'packing_charge': '5',
            'payment_method': 'CASH'
        }),
        content_type='application/json'
    )
    assert response.status_code == 200
    
    # Staff saves a different cart
    response = staff_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Staff Product', 'price': 50.0, 'gst': 12, 'qty': 2, 'stock': 50, 'disc': 0, 'isFree': False}],
            'customer': {'name': 'Staff Customer', 'employee_id': 'STF-001'},
            'discount_percent': '0',
            'shipping_charge': '0',
            'packing_charge': '0',
            'payment_method': 'UPI'
        }),
        content_type='application/json'
    )
    assert response.status_code == 200
    
    # Load admin cart
    response = admin_client.get('/api/cart/load')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['cart'][0]['name'] == 'Admin Product'
    assert data['customer']['name'] == 'Admin Customer'
    assert data['payment_method'] == 'CASH'
    
    # Load staff cart
    response = staff_client.get('/api/cart/load')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['cart'][0]['name'] == 'Staff Product'
    assert data['customer']['name'] == 'Staff Customer'
    assert data['payment_method'] == 'UPI'


def test_api_cart_clear_requires_auth(client):
    """Unauthenticated request should be rejected."""
    response = client.post('/api/cart/clear')
    assert response.status_code == 302


def test_api_cart_clear_works(admin_client):
    """Clearing cart removes saved data."""
    # Save a cart first
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Product A', 'price': 100.0, 'gst': 18, 'qty': 1, 'stock': 100, 'disc': 0, 'isFree': False}],
            'customer': {'name': 'Test Customer', 'employee_id': 'ADM-001'},
            'discount_percent': '10',
            'shipping_charge': '50',
            'packing_charge': '20',
            'payment_method': 'CASH'
        }),
        content_type='application/json'
    )
    assert response.status_code == 200
    
    # Verify cart exists
    response = admin_client.get('/api/cart/load')
    data = json.loads(response.data)
    assert len(data['cart']) == 1
    
    # Clear the cart
    response = admin_client.post('/api/cart/clear')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True
    
    # Verify cart is empty
    response = admin_client.get('/api/cart/load')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['cart'] == []
    assert data.get('customer') is None
    assert data.get('discount_percent') is None


def test_api_cart_clear_empty_cart(admin_client):
    """Clearing empty cart succeeds."""
    response = admin_client.post('/api/cart/clear')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True


def test_api_cart_clear_only_affects_current_user(admin_client, staff_client):
    """Clearing cart only affects current user."""
    # Both users save carts
    admin_client.post('/api/cart/save',
        data=json.dumps({'cart': [{'name': 'Admin Product', 'price': 100.0, 'gst': 18, 'qty': 1, 'stock': 100, 'disc': 0, 'isFree': False}]}),
        content_type='application/json'
    )
    staff_client.post('/api/cart/save',
        data=json.dumps({'cart': [{'name': 'Staff Product', 'price': 50.0, 'gst': 12, 'qty': 1, 'stock': 50, 'disc': 0, 'isFree': False}]}),
        content_type='application/json'
    )
    
    # Admin clears their cart
    response = admin_client.post('/api/cart/clear')
    assert response.status_code == 200
    
    # Admin cart is empty
    response = admin_client.get('/api/cart/load')
    data = json.loads(response.data)
    assert data['cart'] == []
    
    # Staff cart still exists
    response = staff_client.get('/api/cart/load')
    data = json.loads(response.data)
    assert len(data['cart']) == 1
    assert data['cart'][0]['name'] == 'Staff Product'