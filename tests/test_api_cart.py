"""Tests for /api/cart/save validation."""
import json
import pytest


def test_api_cart_save_valid(admin_client):
    """Valid cart data should save successfully."""
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [
                {'name': 'Product A', 'price': 100.0, 'gst': 18, 'qty': 2, 'stock': 100, 'disc': 0, 'isFree': False}
            ],
            'customer': {'name': 'Test Customer', 'employee_id': 'EMP-001'},
            'discount_percent': '10',
            'shipping_charge': '50',
            'packing_charge': '20',
            'payment_method': 'CASH'
        }),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True


def test_api_cart_save_missing_json(admin_client):
    """Missing/invalid JSON should return 400."""
    response = admin_client.post('/api/cart/save',
        data='not valid json',
        content_type='application/json'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['ok'] is False
    assert 'error' in data


def test_api_cart_save_cart_not_array(admin_client):
    """cart must be an array."""
    response = admin_client.post('/api/cart/save',
        data=json.dumps({'cart': 'not an array'}),
        content_type='application/json'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['ok'] is False
    assert 'cart must be an array' in data['error']


def test_api_cart_save_invalid_item_structure(admin_client):
    """Invalid cart item structure returns 400."""
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'price': 100, 'gst': 18, 'qty': 1, 'stock': 100, 'disc': 0, 'isFree': False}]
        }),
        content_type='application/json'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['ok'] is False
    assert 'name' in data['error']


def test_api_cart_save_invalid_quantity(admin_client):
    """Invalid quantity returns 400."""
    # Zero quantity
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Product A', 'price': 100, 'gst': 18, 'qty': 0, 'stock': 100, 'disc': 0, 'isFree': False}]
        }),
        content_type='application/json'
    )
    assert response.status_code == 400

    # Negative quantity
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Product A', 'price': 100, 'gst': 18, 'qty': -1, 'stock': 100, 'disc': 0, 'isFree': False}]
        }),
        content_type='application/json'
    )
    assert response.status_code == 400

    # Non-numeric quantity
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Product A', 'price': 100, 'gst': 18, 'qty': 'abc', 'stock': 100, 'disc': 0, 'isFree': False}]
        }),
        content_type='application/json'
    )
    assert response.status_code == 400


def test_api_cart_save_invalid_discount(admin_client):
    """Invalid discount returns 400."""
    # Discount > 100
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Product A', 'price': 100, 'gst': 18, 'qty': 1, 'stock': 100, 'disc': 150, 'isFree': False}]
        }),
        content_type='application/json'
    )
    assert response.status_code == 400

    # Negative discount
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Product A', 'price': 100, 'gst': 18, 'qty': 1, 'stock': 100, 'disc': -10, 'isFree': False}]
        }),
        content_type='application/json'
    )
    assert response.status_code == 400

    # Non-numeric discount
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [{'name': 'Product A', 'price': 100, 'gst': 18, 'qty': 1, 'stock': 100, 'disc': 'abc', 'isFree': False}]
        }),
        content_type='application/json'
    )
    assert response.status_code == 400


def test_api_cart_save_oversized_payload(admin_client):
    """Oversized payload is rejected."""
    # Create a cart with too many items (over 1000)
    large_cart = [{'name': f'Product {i}', 'price': 100, 'gst': 18, 'qty': 1, 'stock': 100, 'disc': 0, 'isFree': False}
                  for i in range(1001)]

    response = admin_client.post('/api/cart/save',
        data=json.dumps({'cart': large_cart}),
        content_type='application/json'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['ok'] is False
    assert 'Too many cart items' in data['error']


def test_api_cart_save_valid_continues_working(admin_client):
    """Existing valid POS draft behavior continues working."""
    # Save a valid cart
    response = admin_client.post('/api/cart/save',
        data=json.dumps({
            'cart': [
                {'name': 'Product A', 'price': 100.0, 'gst': 18, 'qty': 2, 'stock': 100, 'disc': 0, 'isFree': False},
                {'name': 'Product B', 'price': 50.0, 'gst': 12, 'qty': 1, 'stock': 50, 'disc': 5, 'isFree': False}
            ],
            'customer': {'name': 'Test Customer', 'employee_id': 'EMP-001'},
            'discount_percent': '10',
            'shipping_charge': '50',
            'packing_charge': '20',
            'payment_method': 'CASH'
        }),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True

    # Load the cart back
    response = admin_client.get('/api/cart/load')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['cart']) == 2
    assert data['customer']['name'] == 'Test Customer'
    assert data['discount_percent'] == '10'
    assert data['payment_method'] == 'CASH'