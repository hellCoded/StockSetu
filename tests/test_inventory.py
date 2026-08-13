import pytest

def test_stock_in(staff_client, manager_client):
    manager_client.post('/products/add', data={
        'product_name': 'Steel Bolts',
        'category': 'Hardware',
        'unit': 'boxes',
        'quantity': '10',
        'price': '8.00'
    }, follow_redirects=True)
    
    response = staff_client.post('/inventory/stock-in', data={
        'product_name': 'Steel Bolts',
        'quantity': '25',
        'reason': 'New batch received'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"35" in response.data  # 10 + 25 = 35

def test_stock_out_success(staff_client, manager_client):
    manager_client.post('/products/add', data={
        'product_name': 'Copper Wire',
        'category': 'Electrical',
        'unit': 'meters',
        'quantity': '100',
        'price': '2.50'
    }, follow_redirects=True)
    
    response = staff_client.post('/inventory/stock-out', data={
        'product_name': 'Copper Wire',
        'quantity': '30',
        'reason': 'Dispatched for Job #12'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"70" in response.data  # 100 - 30 = 70

def test_stock_out_insufficient_stock(staff_client, manager_client):
    manager_client.post('/products/add', data={
        'product_name': 'Limited Sensor',
        'category': 'Electronics',
        'unit': 'pcs',
        'quantity': '5',
        'price': '55.00'
    }, follow_redirects=True)
    
    response = staff_client.post('/inventory/stock-out', data={
        'product_name': 'Limited Sensor',
        'quantity': '10',  # Requesting 10 when only 5 exist
        'reason': 'Excess order'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Insufficient stock" in response.data

def test_stock_adjustment_mandatory_reason(manager_client):
    manager_client.post('/products/add', data={
        'product_name': 'Audit Item',
        'category': 'Misc',
        'unit': 'pcs',
        'quantity': '50',
        'price': '1.00'
    }, follow_redirects=True)
    
    # Missing reason should fail
    fail_res = manager_client.post('/inventory/adjust', data={
        'product_name': 'Audit Item',
        'target_quantity': '42',
        'reason': ''
    }, follow_redirects=True)
    assert b"mandatory reason" in fail_res.data
    
    # Valid adjustment
    success_res = manager_client.post('/inventory/adjust', data={
        'product_name': 'Audit Item',
        'target_quantity': '42',
        'reason': 'Physical count corrected following annual audit'
    }, follow_redirects=True)
    assert success_res.status_code == 200
    assert b"42" in success_res.data

def test_status_badge_transitions(manager_client, staff_client):
    manager_client.post('/products/add', data={
        'product_name': 'Status Widget',
        'category': 'Testing',
        'unit': 'pcs',
        'quantity': '20',
        'price': '5.00'
    }, follow_redirects=True)
    
    # Initial status: LOW STOCK (5 <= 5, hardcoded qty)
    res1 = staff_client.get('/products/Status Widget', follow_redirects=True)
    assert b"LOW STOCK" in res1.data
    
    # Stock in 10 -> quantity becomes 15 (15 > 5 -> IN STOCK)
    staff_client.post('/inventory/stock-in', data={
        'product_name': 'Status Widget',
        'quantity': '10',
        'reason': 'Restock'
    }, follow_redirects=True)
    res2 = staff_client.get('/products/Status Widget', follow_redirects=True)
    assert b"IN STOCK" in res2.data
    
    # Stock out 12 -> quantity becomes 3 (3 <= 5 -> LOW STOCK)
    staff_client.post('/inventory/stock-out', data={
        'product_name': 'Status Widget',
        'quantity': '12',
        'reason': 'Partial usage'
    }, follow_redirects=True)
    res3 = staff_client.get('/products/Status Widget', follow_redirects=True)
    assert b"LOW STOCK" in res3.data
    
    # Stock out remaining 3 -> quantity becomes 0 (OUT OF STOCK)
    staff_client.post('/inventory/stock-out', data={
        'product_name': 'Status Widget',
        'quantity': '3',
        'reason': 'Emptied stock'
    }, follow_redirects=True)
    res4 = staff_client.get('/products/Status Widget', follow_redirects=True)
    assert b"OUT OF STOCK" in res4.data
