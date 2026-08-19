import pytest
from datetime import datetime, timezone
from inventory_app.services.billing_service import get_reconciliation_report

def _seed_product(db, name="Steel Rod", price="500.00", gst="18", hsn="7214"):
    db.products.insert_one({
        "product_name": name,
        "product_name_lower": name.lower(),
        "category": "Hardware",
        "description": "",
        "quantity": 100.0,
        "unit": "pcs",
        "price": float(price),
        "gst_rate": float(gst),
        "hsn_code": hsn,
        "minimum_stock": 5,
        "location": "",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    })
    return name

def test_bill_creation_deducts_stock_and_computes_gst(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _seed_product(db)

    response = staff_client.post('/billing/create', data={
        'csrf_token': 'x',
        'customer_name': 'Ramesh Kumar',
        'customer_phone': '9876543210',
        'payment_method': 'UPI',
        'item_name[]': ['Steel Rod'],
        'item_quantity[]': ['2']
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"INV/" in response.data

    bill = db.invoices.find_one({"customer_name": "Ramesh Kumar"})
    assert bill is not None
    assert bill["bill_number"].startswith("INV/")
    assert bill["subtotal"] == 1000.0
    assert bill["gst_total"] == 180.0
    assert bill["cgst_total"] == 90.0
    assert bill["sgst_total"] == 90.0
    assert bill["grand_total"] == 1180.0
    assert bill["line_items"][0]["hsn_code"] == "7214"

    product = db.products.find_one({"product_name": "Steel Rod"})
    assert product["quantity"] == 98.0

    tx = db.inventory_transactions.find_one({"transaction_type": "BILL_SALE"})
    assert tx is not None
    assert tx["quantity"] == 2.0
    assert tx.get("bill_number") == bill["bill_number"]

def test_invoice_numbers_are_sequential(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Item A")
    _seed_product(db, name="Item B")

    for i in range(2):
        staff_client.post('/billing/create', data={
            'customer_name': 'Customer',
            'item_name[]': [f'Item {"A" if i == 0 else "B"}'],
            'item_quantity[]': ['1']
        }, follow_redirects=True)

    bills = list(db.invoices.find().sort("created_at", 1))
    assert len(bills) == 2
    numbers = [b["bill_number"] for b in bills]
    assert numbers == sorted(numbers)

def test_bill_fails_on_insufficient_stock(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Limited Item")

    response = staff_client.post('/billing/create', data={
        'customer_name': 'Ramesh',
        'item_name[]': ['Limited Item'],
        'item_quantity[]': ['500']
    }, follow_redirects=True)

    assert b"Insufficient stock" in response.data
    assert db.invoices.count_documents({}) == 0
    product = db.products.find_one({"product_name": "Limited Item"})
    assert product["quantity"] == 100.0

def test_bill_requires_customer_name_and_items(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _seed_product(db)

    response = staff_client.post('/billing/create', data={
        'customer_name': '',
        'item_name[]': ['Steel Rod'],
        'item_quantity[]': ['1']
    }, follow_redirects=True)
    assert b"Customer name is required" in response.data

    response = staff_client.post('/billing/create', data={
        'customer_name': 'Walk-in',
        'item_name[]': [''],
        'item_quantity[]': ['1']
    }, follow_redirects=True)
    assert b"at least one item" in response.data.lower() or b"At least one item" in response.data

def test_invalid_gstin_rejected(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _seed_product(db)

    response = staff_client.post('/billing/create', data={
        'customer_name': 'Ramesh',
        'customer_gstin': 'INVALID-GSTIN',
        'item_name[]': ['Steel Rod'],
        'item_quantity[]': ['1']
    }, follow_redirects=True)

    assert b"GSTIN is invalid" in response.data
    assert db.invoices.count_documents({}) == 0

def test_bill_history_and_detail_pages(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _seed_product(db)

    staff_client.post('/billing/create', data={
        'customer_name': 'Ram Sharma',
        'item_name[]': ['Steel Rod'],
        'item_quantity[]': ['1']
    }, follow_redirects=True)

    history = staff_client.get('/billing/bills')
    assert history.status_code == 200
    assert b"INV/" in history.data
    assert b"Ram Sharma" in history.data

    bill = db.invoices.find_one({"customer_name": "Ram Sharma"})
    detail = staff_client.get(f"/billing/bills/{bill['_id']}")
    assert detail.status_code == 200
    assert b"TAX INVOICE" in detail.data.upper() or b"Tax Invoice" in detail.data

def test_pos_page_renders_products(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _seed_product(db)

    response = staff_client.get('/billing')
    assert response.status_code == 200
    assert b"Steel Rod" in response.data
    assert b"Billing" in response.data

def test_gst_fields_on_product_forms(manager_client):
    response = manager_client.post('/products/add', data={
        'product_name': 'GST Bracket',
        'category': 'Hardware',
        'unit': 'pcs',
        'quantity': '10',
        'price': '100.00',
        'gst_rate': '12',
        'hsn_code': '7326'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"GST Bracket" in response.data
    assert b"12" in response.data
    assert b"7326" in response.data


# ──────────────────────────────────────────────────────────────────────
# Payment recording + bill detail rendering tests
# ──────────────────────────────────────────────────────────────────────

def _create_bill(db, client, customer="Test Customer", qty="1", payment_method="CREDIT"):
    """Helper: seed product, create bill, return bill_id string. Defaults to CREDIT so bill is PARTIAL/unpaid."""
    _seed_product(db)
    client.post('/billing/create', data={
        'customer_name': customer,
        'customer_phone': '9000000001',
        'payment_method': payment_method,
        'due_date': '2026-12-31',
        'item_name[]': ['Steel Rod'],
        'item_quantity[]': [qty],
    }, follow_redirects=True)
    bill = db.invoices.find_one({"customer_name": customer})
    return str(bill["_id"])


def test_record_full_payment_updates_bill(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    bill_id = _create_bill(db, staff_client, "Pay Full")
    bill = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})
    grand_total = bill["grand_total"]

    resp = staff_client.post(f'/billing/bills/{bill_id}/pay', data={
        'csrf_token': 'x',
        'amount': str(grand_total),
        'method': 'CASH',
        'reference': 'CASH-001',
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})
    assert updated["payment_status"] == "PAID"
    assert updated["amount_paid"] == grand_total
    assert updated["amount_due"] == 0


def test_record_partial_payment_updates_bill(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    bill_id = _create_bill(db, staff_client, "Pay Partial")
    bill = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})
    grand_total = bill["grand_total"]
    half = round(grand_total / 2, 2)

    resp = staff_client.post(f'/billing/bills/{bill_id}/pay', data={
        'csrf_token': 'x',
        'amount': str(half),
        'method': 'UPI',
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})
    assert updated["payment_status"] == "PARTIAL"
    assert updated["amount_paid"] == half
    assert updated["amount_due"] > 0



def test_cannot_overpay_bill(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    bill_id = _create_bill(db, staff_client, "No Overpay")
    bill = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})
    over = bill["grand_total"] + 100

    resp = staff_client.post(f'/billing/bills/{bill_id}/pay', data={
        'csrf_token': 'x', 'amount': str(over), 'method': 'CASH',
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})
    assert updated["payment_status"] == "PARTIAL"


def test_bill_detail_shows_status_color(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    bill_id = _create_bill(db, staff_client, "Color Test")

    detail = staff_client.get(f'/billing/bills/{bill_id}')
    assert detail.status_code == 200
    assert b"PARTIAL" in detail.data


def test_bills_list_renders_with_status(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _create_bill(db, staff_client, "List Test")

    resp = staff_client.get('/billing/bills')
    assert resp.status_code == 200
    assert b"List Test" in resp.data
    assert b"INV/" in resp.data


def test_paid_bill_shows_paid_badge(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    bill_id = _create_bill(db, staff_client, "Badge Test")
    bill = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})

    staff_client.post(f'/billing/bills/{bill_id}/pay', data={
        'csrf_token': 'x',
        'amount': str(bill["grand_total"]),
        'method': 'UPI',
    }, follow_redirects=True)

    detail = staff_client.get(f'/billing/bills/{bill_id}')
    assert detail.status_code == 200
    assert b"PAID" in detail.data
    assert b"#15803d" in detail.data or b"color:#15803d" in detail.data


def test_reject_payment_on_already_paid_bill(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    bill_id = _create_bill(db, staff_client, "Already Paid")
    bill = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})

    staff_client.post(f'/billing/bills/{bill_id}/pay', data={
        'csrf_token': 'x',
        'amount': str(bill["grand_total"]),
        'method': 'CASH',
    }, follow_redirects=True)

    resp = staff_client.post(f'/billing/bills/{bill_id}/pay', data={
        'csrf_token': 'x', 'amount': '100', 'method': 'CASH',
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})
    assert updated["payment_status"] == "PAID"


def test_reconciliation_no_false_missing_sale_tx(staff_client, mock_mongo):
    """A bill created through the normal flow must not be flagged as
    MISSING_SALE_TX — its BILL_SALE transactions now carry bill_number."""
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Recon Bar")
    bill_id = _create_bill(db, staff_client, "Recon Customer")

    bill = db.invoices.find_one({"_id": __import__("bson").ObjectId(bill_id)})
    assert bill is not None

    anomalies = get_reconciliation_report()
    relevant = [
        a for a in anomalies
        if a.get("type") == "MISSING_SALE_TX" and a.get("bill_number") == bill["bill_number"]
    ]
    assert relevant == []


def test_reconciliation_detects_missing_sale_tx(app):
    """A bill line with no matching BILL_SALE transaction must be flagged.
    Depends on the app fixture so the global cache is flushed and get_db()
    resolves to the fresh test database."""
    from inventory_app.database import get_db
    db = get_db()
    now = datetime.now(timezone.utc)
    db.invoices.insert_one({
        "bill_number": "INV/MANUAL/1",
        "customer_name": "Manual",
        "line_items": [{
            "product_name": "Ghost Item",
            "quantity": 1.0,
            "unit_price": 100.0,
            "line_discount_amount": 0.0,
            "taxable": 100.0,
            "gst_amount": 18.0,
            "line_total": 118.0,
            "is_free": False,
            "refund_quantity": 0.0,
        }],
        "subtotal": 100.0,
        "grand_total": 118.0,
        "payment_status": "PAID",
        "amount_paid": 118.0,
        "amount_due": 0.0,
        "discount_amount": 0.0,
        "created_by": "teststaff",
        "created_at": now,
    })

    anomalies = get_reconciliation_report()
    assert any(
        a.get("type") == "MISSING_SALE_TX" and a.get("bill_number") == "INV/MANUAL/1"
        for a in anomalies
    )


def test_employee_purchase_with_staff_discount_and_salary_deduction(staff_client, mock_mongo):
    from inventory_app.services.billing_service import create_bill, get_employee_purchases
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Staff Steel Rods", price=1000.0, gst=18)

    customer_data = {
        'customer_name': 'Test Staff Member',
        'customer_phone': '9876543210',
        'is_employee_purchase': True,
        'buyer_employee_id': 'STF-001',
        'staff_discount_percent': 10.0,
        'payment_method': 'SALARY_DEDUCTION',
        'discount_percent': 0.0,
    }
    items = [{
        'product_name': 'Staff Steel Rods',
        'quantity': 1.0,
    }]

    success, msg, bill = create_bill(customer_data, items, performed_by='ADM-001')
    assert success is True
    assert bill["is_employee_purchase"] is True
    assert bill["buyer_employee_id"] == "STF-001"
    assert bill["payment_method"] == "SALARY_DEDUCTION"
    assert bill["payment_status"] == "PAID"
    # Taxable subtotal is 1000. With 10% discount: 900. GST 18%: 162. Grand Total: 1062.
    assert bill["discount_percent"] == 10.0
    assert bill["discount_amount"] == 100.0
    assert bill["grand_total"] == 1080.0

    # Query employee purchases
    purchases = get_employee_purchases("STF-001")
    assert len(purchases) >= 1
    assert any(p["bill_number"] == bill["bill_number"] for p in purchases)


def test_profile_displays_employee_purchases(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Profile Cement", price=500.0, gst=18)

    # Post bill for staff
    resp = staff_client.post('/billing/create', data={
        'csrf_token': 'x',
        'customer_name': 'Test Staff',
        'customer_phone': '9998887776',
        'is_employee_purchase': '1',
        'buyer_employee_id': 'STF-001',
        'staff_discount_percent': '10',
        'payment_method': 'SALARY_DEDUCTION',
        'discount_percent': '10',
        'item_name[]': ['Profile Cement'],
        'item_quantity[]': ['2'],
    }, follow_redirects=True)
    assert resp.status_code == 200

    # View profile as staff
    profile_resp = staff_client.get('/profile')
    assert profile_resp.status_code == 200
    assert b"My Store Purchases" in profile_resp.data
    assert b"Salary Deduction" in profile_resp.data
    assert b"Profile Cement" in profile_resp.data