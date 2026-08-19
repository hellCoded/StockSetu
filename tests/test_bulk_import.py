def test_bulk_import_confirm_creates_new_products(admin_client, mock_mongo):
    """Items mapped to __new__ create products with bill data + user-supplied params."""
    db = mock_mongo['inventory_test_db']
    with admin_client.session_transaction() as sess:
        sess['bulk_import_items'] = [
            {'item_name': 'Steel Bolts M10', 'quantity': 500.0, 'unit': 'PCS', 'hsn_code': '7318'},
            {'item_name': 'Copper Wire 2.5sqmm', 'quantity': 200.0, 'unit': 'MTR', 'hsn_code': '7408'},
        ]

    response = admin_client.post('/inventory/bulk-stock-in/confirm', data={
        'mapping[]': ['__new__', '__new__'],
        'item_name[]': ['Steel Bolts M10', 'Copper Wire 2.5sqmm'],
        'item_qty[]': ['500', '200'],
        'item_unit[]': ['PCS', 'MTR'],
        'item_hsn[]': ['7318', '7408'],
        'new_category[]': ['Fasteners', 'Electrical'],
        'new_price[]': ['10.5', '120.0'],
        'new_gst[]': ['18', '18'],
        'new_location[]': ['Rack A1', 'Rack B2'],
        'new_desc[]': ['From supplier bill', 'From supplier bill'],
        'reason': 'Bulk import test',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Created 2 new product(s)" in response.data

    bolts = db.products.find_one({'product_name': 'Steel Bolts M10'})
    assert bolts is not None
    assert float(bolts['quantity']) == 500.0
    assert bolts['category'] == 'Fasteners'
    assert bolts['unit'] == 'PCS'
    assert bolts['hsn_code'] == '7318'

    wire = db.products.find_one({'product_name': 'Copper Wire 2.5sqmm'})
    assert wire is not None
    assert float(wire['quantity']) == 200.0
    assert wire['category'] == 'Electrical'
    assert wire['unit'] == 'MTR'

    txs = db.inventory_transactions.find({}).sort('created_at', -1)
    txs = list(txs)
    assert any(t['product_name'] == 'Steel Bolts M10' and t['transaction_type'] == 'INITIAL_STOCK'
               for t in txs)
    assert not any(t['product_name'] == 'Steel Bolts M10' and t['transaction_type'] == 'STOCK_IN'
                   for t in txs)


def test_bulk_import_confirm_stock_in_existing(admin_client, mock_mongo):
    """Items mapped to an existing product are stocked in (not recreated)."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        'product_name': 'Steel Bolts M10',
        'product_name_lower': 'steel bolts m10',
        'category': 'Fasteners',
        'unit': 'PCS',
        'quantity': 5,
        'minimum_stock': 5,
        'price': 10.5,
        'gst_rate': 18,
        'hsn_code': '7318',
        'is_active': True,
    })

    with admin_client.session_transaction() as sess:
        sess['bulk_import_items'] = [
            {'item_name': 'Steel Bolts M10', 'quantity': 500.0, 'unit': 'PCS', 'hsn_code': '7318'},
        ]

    response = admin_client.post('/inventory/bulk-stock-in/confirm', data={
        'mapping[]': ['Steel Bolts M10'],
        'item_name[]': ['Steel Bolts M10'],
        'item_qty[]': ['500'],
        'item_unit[]': ['PCS'],
        'item_hsn[]': ['7318'],
        'reason': 'Bulk import test',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Successfully stocked in 1 item(s)" in response.data

    bolts = db.products.find_one({'product_name': 'Steel Bolts M10'})
    assert float(bolts['quantity']) == 505.0

    txs = db.inventory_transactions.find({}).sort('created_at', -1)
    txs = list(txs)
    assert any(t['product_name'] == 'Steel Bolts M10' and t['transaction_type'] == 'STOCK_IN'
               for t in txs)


def test_bulk_import_confirm_new_missing_category(admin_client, mock_mongo):
    """New product without required category is reported, not created."""
    db = mock_mongo['inventory_test_db']
    with admin_client.session_transaction() as sess:
        sess['bulk_import_items'] = [
            {'item_name': 'Steel Bolts M10', 'quantity': 500.0, 'unit': 'PCS', 'hsn_code': '7318'},
        ]

    response = admin_client.post('/inventory/bulk-stock-in/confirm', data={
        'mapping[]': ['__new__'],
        'item_name[]': ['Steel Bolts M10'],
        'item_qty[]': ['500'],
        'item_unit[]': ['PCS'],
        'item_hsn[]': ['7318'],
        'new_category[]': [''],
        'new_price[]': ['10.5'],
        'new_gst[]': ['18'],
        'new_location[]': ['Rack A1'],
        'new_desc[]': ['From supplier bill'],
        'reason': 'Bulk import test',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Category is required" in response.data
    assert db.products.find_one({'product_name': 'Steel Bolts M10'}) is None


def test_bulk_import_confirm_missing_session(admin_client):
    """Confirm without a prior upload session redirects back to upload."""
    response = admin_client.post('/inventory/bulk-stock-in/confirm', data={
        'mapping[]': ['Steel Bolts M10'],
    }, follow_redirects=False)

    assert response.status_code == 302
    assert '/inventory/bulk-stock-in' in response.headers.get('Location')


def test_bulk_import_confirm_no_items(admin_client):
    """Confirm with no item data at all redirects back to upload."""
    response = admin_client.post('/inventory/bulk-stock-in/confirm', data={
        'mapping[]': ['Steel Bolts M10'],
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"No items to import" in response.data


def test_bulk_import_confirm_from_form_fields(admin_client, mock_mongo):
    """Confirm works from hidden form fields alone (no session dependency)."""
    db = mock_mongo['inventory_test_db']
    response = admin_client.post('/inventory/bulk-stock-in/confirm', data={
        'mapping[]': ['__new__'],
        'item_name[]': ['Steel Bolts M10'],
        'item_qty[]': ['500'],
        'item_unit[]': ['PCS'],
        'item_hsn[]': ['7318'],
        'new_category[]': ['Fasteners'],
        'new_price[]': ['10.5'],
        'new_gst[]': ['18'],
        'new_location[]': ['Rack A1'],
        'new_desc[]': ['From supplier bill'],
        'reason': 'Bulk import test',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Created 1 new product(s)" in response.data
    bolts = db.products.find_one({'product_name': 'Steel Bolts M10'})
    assert bolts is not None
    assert float(bolts['quantity']) == 500.0


def test_bulk_import_confirm_mixed_existing_and_new(admin_client, mock_mongo):
    """Existing items stock in, new items are created in one confirm."""
    db = mock_mongo['inventory_test_db']
    db.products.insert_one({
        'product_name': 'Steel Bolts M10',
        'product_name_lower': 'steel bolts m10',
        'category': 'Fasteners',
        'unit': 'PCS',
        'quantity': 5,
        'minimum_stock': 5,
        'price': 10.5,
        'gst_rate': 18,
        'hsn_code': '7318',
        'is_active': True,
    })

    response = admin_client.post('/inventory/bulk-stock-in/confirm', data={
        'mapping[]': ['Steel Bolts M10', '__new__'],
        'item_name[]': ['Steel Bolts M10', 'Copper Wire 2.5sqmm'],
        'item_qty[]': ['500', '200'],
        'item_unit[]': ['PCS', 'MTR'],
        'item_hsn[]': ['7318', '7408'],
        'new_category[]': ['Electrical'],
        'new_price[]': ['120.0'],
        'new_gst[]': ['18'],
        'new_location[]': ['Rack B2'],
        'new_desc[]': ['From bill'],
        'reason': 'Bulk import test',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Created 1 new product(s)" in response.data
    assert b"Successfully stocked in 2 item(s)" in response.data

    bolts = db.products.find_one({'product_name': 'Steel Bolts M10'})
    assert float(bolts['quantity']) == 505.0

    wire = db.products.find_one({'product_name': 'Copper Wire 2.5sqmm'})
    assert wire is not None
    assert float(wire['quantity']) == 200.0
    assert wire['category'] == 'Electrical'
    assert wire['unit'] == 'MTR'
