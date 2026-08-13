import pytest

def test_create_product_success(manager_client):
    response = manager_client.post('/products/add', data={
        'product_name': '  Industrial Solvent  ',
        'category': 'Chemicals',
        'unit': 'liters',
        'quantity': '100',
        'price': '45.50',
        'location': 'Rack 4A',
        'description': 'High purity solvent'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Industrial Solvent" in response.data
    assert b"100" in response.data

def test_duplicate_product_name_rejection(manager_client):
    # First creation
    manager_client.post('/products/add', data={
        'product_name': 'ABC Cement',
        'category': 'Building',
        'unit': 'bags',
        'quantity': '50',
        'price': '12.00'
    }, follow_redirects=True)
    
    # Duplicate creation with trailing space and different casing
    response = manager_client.post('/products/add', data={
        'product_name': ' abc cement ',
        'category': 'Building',
        'unit': 'bags',
        'quantity': '10',
        'price': '12.00'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"already exists" in response.data

def test_product_search_and_filter(manager_client):
    manager_client.post('/products/add', data={
        'product_name': 'Heavy Duty Drill',
        'category': 'Hardware',
        'unit': 'pcs',
        'quantity': '15',
        'price': '120.00'
    }, follow_redirects=True)
    
    # Flexible keyword search
    response = manager_client.get('/products?q=drill')
    assert response.status_code == 200
    assert b"Heavy Duty Drill" in response.data

def test_edit_product(manager_client):
    manager_client.post('/products/add', data={
        'product_name': 'Safety Goggles',
        'category': 'PPE',
        'unit': 'pcs',
        'quantity': '30',
        'price': '15.00'
    }, follow_redirects=True)
    
    response = manager_client.post('/products/Safety Goggles/edit', data={
        'category': 'PPE & Safety',
        'unit': 'pcs',
        'price': '18.50',
        'description': 'Updated safety goggles'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"PPE &amp; Safety" in response.data or b"PPE & Safety" in response.data

def test_rename_product_admin_only(admin_client, staff_client):
    admin_client.post('/products/add', data={
        'product_name': 'Old Name Tool',
        'category': 'Hardware',
        'unit': 'pcs',
        'quantity': '20',
        'price': '25.00'
    }, follow_redirects=True)
    
    # Staff attempt should be forbidden / redirected
    staff_response = staff_client.post('/products/Old%20Name%20Tool/rename', data={
        'new_product_name': 'Staff Renamed Tool'
    }, follow_redirects=True)
    assert b"Forbidden" in staff_response.data or b"Dashboard" in staff_response.data
    
    # Admin attempt should succeed
    admin_response = admin_client.post('/products/Old%20Name%20Tool/rename', data={
        'new_product_name': 'Brand New Name Tool'
    }, follow_redirects=True)
    assert admin_response.status_code == 200
    assert b"Brand New Name Tool" in admin_response.data

def test_toggle_product_active(manager_client):
    manager_client.post('/products/add', data={
        'product_name': 'Temp Product',
        'category': 'General',
        'unit': 'pcs',
        'quantity': '5',
        'price': '5.00'
    }, follow_redirects=True)
    
    response = manager_client.post('/products/Temp Product/toggle-active', follow_redirects=True)
    assert response.status_code == 200
    assert b"deactivated" in response.data

def test_export_excel_report(manager_client):
    response = manager_client.get('/products/export/excel')
    assert response.status_code == 200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert len(response.data) > 0

def test_export_pdf_report(manager_client):
    response = manager_client.get('/products/export/pdf')
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert len(response.data) > 0

def test_dashboard_chart_aggregations(manager_client, app):
    from inventory_app.services.product_service import (
        get_stock_by_category,
        get_low_stock_by_category,
        get_top_products_stock
    )
    with app.app_context():
        manager_client.post('/products/add', data={
            'product_name': 'Unique Aggregate Product',
            'category': 'AggrCategory',
            'unit': 'pcs',
            'quantity': '15',
            'price': '10.00'
        }, follow_redirects=True)
        
        stock_by_cat = get_stock_by_category()
        low_stock_by_cat = get_low_stock_by_category()
        top_products = get_top_products_stock()
        
        aggr_cat_stock = next((item for item in stock_by_cat if item['category'] == 'AggrCategory'), None)
        assert aggr_cat_stock is not None
        assert aggr_cat_stock['total_stock'] >= 5
        
        aggr_cat_low = next((item for item in low_stock_by_cat if item['category'] == 'AggrCategory'), None)
        assert aggr_cat_low is not None
        assert aggr_cat_low['low_stock_count'] >= 1
        
        has_prod = any(p['product_name'] == 'Unique Aggregate Product' for p in top_products)
        assert has_prod
