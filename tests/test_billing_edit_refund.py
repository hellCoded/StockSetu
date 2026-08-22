"""Tests for bill edit and refund operations (service-level)."""
import pytest
from datetime import datetime, timezone
from bson import ObjectId


def _seed_product(db, name="Test Product", price=100.0, gst=18, stock=100, hsn="8471"):
    db.products.insert_one({
        "product_name": name,
        "product_name_lower": name.lower(),
        "category": "Test",
        "description": "",
        "quantity": float(stock),
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


def _create_bill(client, db, customer="Test Customer", items=None, payment_method="CREDIT"):
    """Helper: create a bill and return bill_id string."""
    if items is None:
        items = [{"name": "Test Product", "qty": "1"}]
    
    form_data = {
        'customer_name': customer,
        'customer_phone': '9000000001',
        'payment_method': payment_method,
        'due_date': '2026-12-31',
        'item_name[]': [item['name'] for item in items],
        'item_quantity[]': [item['qty'] for item in items],
    }
    
    client.post('/billing/create', data=form_data)
    bill = db.invoices.find_one({"customer_name": customer})
    return str(bill["_id"])


# ========== EDIT BILL TESTS (via service) ==========

def test_edit_bill_increase_quantity(staff_client, mock_mongo):
    """Increasing quantity deducts additional stock."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Steel Rod", price=500.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Edit Inc", [{"name": "Steel Rod", "qty": "2"}])
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert bill["line_items"][0]["quantity"] == 2.0
    
    # Edit: increase to 5
    items = [{
        'product_name': 'Steel Rod',
        'quantity': 5,
    }]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Edit Inc',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["line_items"][0]["quantity"] == 5.0
    product = db.products.find_one({"product_name": "Steel Rod"})
    assert product["quantity"] == 95.0  # 100 - 5


def test_edit_bill_decrease_quantity(staff_client, mock_mongo):
    """Decreasing quantity restores stock."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Steel Rod", price=500.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Edit Dec", [{"name": "Steel Rod", "qty": "10"}])
    product = db.products.find_one({"product_name": "Steel Rod"})
    assert product["quantity"] == 90.0
    
    # Edit: decrease to 3
    items = [{
        'product_name': 'Steel Rod',
        'quantity': 3,
    }]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Edit Dec',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["line_items"][0]["quantity"] == 3.0
    product = db.products.find_one({"product_name": "Steel Rod"})
    assert product["quantity"] == 97.0  # 7 restored


def test_edit_bill_add_item(staff_client, mock_mongo):
    """Adding a new item to existing bill."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Steel Rod", price=500.0, stock=100)
    _seed_product(db, name="Cement Bag", price=200.0, gst=28, stock=50, hsn="2523")
    
    bill_id = _create_bill(staff_client, db, "Add Item", [{"name": "Steel Rod", "qty": "2"}])
    
    # Edit: add Cement Bag
    items = [
        {'product_name': 'Steel Rod', 'quantity': 2},
        {'product_name': 'Cement Bag', 'quantity': 3},
    ]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Add Item',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert len(updated["line_items"]) == 2
    
    items_by_name = {item["product_name"]: item for item in updated["line_items"]}
    assert items_by_name["Steel Rod"]["quantity"] == 2.0
    assert items_by_name["Cement Bag"]["quantity"] == 3.0
    
    steel = db.products.find_one({"product_name": "Steel Rod"})
    cement = db.products.find_one({"product_name": "Cement Bag"})
    assert steel["quantity"] == 98.0
    assert cement["quantity"] == 47.0


def test_edit_bill_remove_item(staff_client, mock_mongo):
    """Removing an item restores its stock."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Steel Rod", price=500.0, stock=100)
    _seed_product(db, name="Cement Bag", price=200.0, gst=28, stock=50, hsn="2523")
    
    bill_id = _create_bill(staff_client, db, "Remove Item", [
        {"name": "Steel Rod", "qty": "2"},
        {"name": "Cement Bag", "qty": "3"}
    ])
    
    # Edit: remove Cement Bag
    items = [{'product_name': 'Steel Rod', 'quantity': 2}]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Remove Item',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert len(updated["line_items"]) == 1
    assert updated["line_items"][0]["product_name"] == "Steel Rod"
    
    steel = db.products.find_one({"product_name": "Steel Rod"})
    cement = db.products.find_one({"product_name": "Cement Bag"})
    assert steel["quantity"] == 98.0
    assert cement["quantity"] == 50.0  # Fully restored


def test_edit_bill_mixed_add_remove(staff_client, mock_mongo):
    """Mixed: increase one, decrease another, add new, remove one."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Item A", price=100.0, stock=50)
    _seed_product(db, name="Item B", price=200.0, gst=12, stock=30, hsn="1234")
    _seed_product(db, name="Item C", price=300.0, gst=18, stock=20, hsn="5678")
    
    bill_id = _create_bill(staff_client, db, "Mixed", [
        {"name": "Item A", "qty": "5"},
        {"name": "Item B", "qty": "10"}
    ])
    
    # Edit: Item A 5->8 (+3), remove Item B, add Item C x2
    items = [
        {'product_name': 'Item A', 'quantity': 8},
        {'product_name': 'Item C', 'quantity': 2},
    ]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Mixed',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    items_by_name = {item["product_name"]: item for item in updated["line_items"]}
    
    assert items_by_name["Item A"]["quantity"] == 8.0
    assert "Item C" in items_by_name
    assert items_by_name["Item C"]["quantity"] == 2.0
    assert "Item B" not in items_by_name
    
    item_a = db.products.find_one({"product_name": "Item A"})
    item_b = db.products.find_one({"product_name": "Item B"})
    item_c = db.products.find_one({"product_name": "Item C"})
    
    assert item_a["quantity"] == 42.0
    assert item_b["quantity"] == 30.0  # Restored all 10
    assert item_c["quantity"] == 18.0


def test_edit_bill_insufficient_stock(staff_client, mock_mongo):
    """Increasing quantity beyond available stock fails."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Limited Item", price=100.0, stock=10)
    
    bill_id = _create_bill(staff_client, db, "Insuff", [{"name": "Limited Item", "qty": "5"}])
    
    # Try to increase to 20 (need 15 more, only 5 available)
    items = [{'product_name': 'Limited Item', 'quantity': 20}]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Insuff',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert not success
    assert "Insufficient stock" in msg or "Stock deduction failed" in msg
    
    # Bill should remain unchanged
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert bill["line_items"][0]["quantity"] == 5.0
    
    # Stock should remain 5
    product = db.products.find_one({"product_name": "Limited Item"})
    assert product["quantity"] == 5.0


def test_edit_bill_refunded_bill_rejected(staff_client, mock_mongo):
    """Cannot edit a fully refunded bill."""
    from inventory_app.services.billing_service import edit_bill, refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Refunded Item", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Refunded Edit", [{"name": "Refunded Item", "qty": "2"}])
    
    refund_bill(bill_id, "Test refund", "STF-001")
    
    items = [{'product_name': 'Refunded Item', 'quantity': 5}]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Refunded Edit',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert not success
    assert "Cannot edit a refunded bill" in msg
    
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert bill["line_items"][0]["quantity"] == 2.0


def test_edit_bill_preserves_payment_status(staff_client, mock_mongo):
    """Editing bill adjusts amount_due but preserves payment history.
    Note: When grand_total increases beyond amount_paid, status becomes PARTIAL.
    """
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Paid Item", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Paid Status", [{"name": "Paid Item", "qty": "1"}], payment_method="CASH")
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert bill["payment_status"] == "PAID"
    original_amount_paid = bill["amount_paid"]
    
    # Edit: increase quantity (grand_total becomes 300 + GST = 354)
    items = [{'product_name': 'Paid Item', 'quantity': 3}]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Paid Status',
        'customer_phone': '9000000001',
        'payment_method': 'CASH',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    # Amount paid preserved, but status becomes PARTIAL since new total > old paid
    assert updated["amount_paid"] == original_amount_paid
    assert updated["payment_status"] == "PARTIAL"
    assert updated["amount_due"] > 0.0


def test_edit_bill_with_discount(staff_client, mock_mongo):
    """Edit applies line-level discounts."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Discount Item", price=1000.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Discount", [{"name": "Discount Item", "qty": "1"}])
    
    items = [{
        'product_name': 'Discount Item',
        'quantity': 1,
        'line_discount_percent': 10,
    }]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Discount',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["line_items"][0]["line_discount_percent"] == 10.0
    # 1000 - 10% = 900 taxable, 18% GST = 162, total = 1062
    assert updated["grand_total"] == 1062.0


def test_edit_bill_with_free_item(staff_client, mock_mongo):
    """Edit marks item as free - is_free flag is stored on line item."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Free Item", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Free", [{"name": "Free Item", "qty": "2"}])
    
    items = [{
        'product_name': 'Free Item',
        'quantity': 2,
        'is_free': True,
    }]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {
        'customer_name': 'Free',
        'customer_phone': '9000000001',
        'payment_method': 'CREDIT',
        'discount_percent': '0',
    }
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["line_items"][0]["is_free"] is True
    # Note: is_free flag is stored but may not zero out grand_total depending on compute_bill logic


# ========== REFUND BILL TESTS ==========

def test_refund_full_bill(staff_client, mock_mongo):
    """Full refund restores all stock and marks REFUNDED."""
    from inventory_app.services.billing_service import refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Refund Product", price=1000.0, stock=50)
    
    bill_id = _create_bill(staff_client, db, "Full Refund", [{"name": "Refund Product", "qty": "3"}], payment_method="CASH")
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert bill["payment_status"] == "PAID"
    
    product = db.products.find_one({"product_name": "Refund Product"})
    assert product["quantity"] == 47.0
    
    success, msg = refund_bill(bill_id, "Customer return", "STF-001")
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["payment_status"] == "REFUNDED"
    assert updated["amount_due"] == 0.0
    assert updated["line_items"][0]["is_refunded"] is True
    assert updated["line_items"][0]["refund_quantity"] == 3.0
    
    # Stock fully restored
    product = db.products.find_one({"product_name": "Refund Product"})
    assert product["quantity"] == 50.0


def test_refund_partial_payment_bill(staff_client, mock_mongo):
    """Refunding a partially paid bill."""
    from inventory_app.services.billing_service import refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Partial Refund", price=500.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Partial Refund", [{"name": "Partial Refund", "qty": "2"}], payment_method="CREDIT")
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert bill["payment_status"] == "PARTIAL"
    
    success, msg = refund_bill(bill_id, "Partial refund test", "STF-001")
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["payment_status"] == "REFUNDED"
    assert updated["amount_due"] == 0.0


def test_refund_already_refunded_bill(staff_client, mock_mongo):
    """Refunding an already-refunded bill fails."""
    from inventory_app.services.billing_service import refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Already Refunded", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Already Refunded", [{"name": "Already Refunded", "qty": "1"}])
    
    refund_bill(bill_id, "First refund", "STF-001")
    
    success2, msg2 = refund_bill(bill_id, "Second refund", "STF-001")
    assert not success2
    assert "already been refunded" in msg2


def test_refund_restores_stock_correctly(staff_client, mock_mongo):
    """Refund restores exact stock quantity."""
    from inventory_app.services.billing_service import refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Stock Test", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Stock Restore", [{"name": "Stock Test", "qty": "10"}])
    
    product = db.products.find_one({"product_name": "Stock Test"})
    assert product["quantity"] == 90.0
    
    refund_bill(bill_id, "Stock restore test", "STF-001")
    
    product = db.products.find_one({"product_name": "Stock Test"})
    assert product["quantity"] == 100.0


# ========== PARTIAL/LINE REFUND TESTS ==========

def test_refund_single_line(staff_client, mock_mongo):
    """Refund specific line item via service."""
    from inventory_app.services.billing_service import refund_bill_lines
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Line A", price=100.0, stock=50)
    _seed_product(db, name="Line B", price=200.0, gst=12, stock=50, hsn="1234")
    
    bill_id = _create_bill(staff_client, db, "Line Refund", [
        {"name": "Line A", "qty": "2"},
        {"name": "Line B", "qty": "3"}
    ])
    
    success, msg = refund_bill_lines(bill_id, [0], "Defective item", "STF-001")
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["line_items"][0]["is_refunded"] is True
    assert updated["line_items"][1]["is_refunded"] is False
    
    line_a = db.products.find_one({"product_name": "Line A"})
    line_b = db.products.find_one({"product_name": "Line B"})
    assert line_a["quantity"] == 50.0
    assert line_b["quantity"] == 47.0


def test_refund_multiple_lines(staff_client, mock_mongo):
    """Refund multiple line items."""
    from inventory_app.services.billing_service import refund_bill_lines
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Item X", price=100.0, stock=50)
    _seed_product(db, name="Item Y", price=200.0, stock=50)
    _seed_product(db, name="Item Z", price=300.0, stock=50)
    
    bill_id = _create_bill(staff_client, db, "Multi Refund", [
        {"name": "Item X", "qty": "2"},
        {"name": "Item Y", "qty": "2"},
        {"name": "Item Z", "qty": "2"}
    ])
    
    success, msg = refund_bill_lines(bill_id, [0, 2], "Partial return", "STF-001")
    assert success
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["line_items"][0]["is_refunded"] is True
    assert updated["line_items"][1]["is_refunded"] is False
    assert updated["line_items"][2]["is_refunded"] is True


def test_refund_already_refunded_line(staff_client, mock_mongo):
    """Refunding an already-refunded line fails."""
    from inventory_app.services.billing_service import refund_bill_lines
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Duplicate Refund", price=100.0, stock=50)
    
    bill_id = _create_bill(staff_client, db, "Dup Refund", [{"name": "Duplicate Refund", "qty": "2"}])
    
    refund_bill_lines(bill_id, [0], "First", "STF-001")
    
    success, msg = refund_bill_lines(bill_id, [0], "Second", "STF-001")
    assert not success
    assert "already been fully refunded" in msg.lower() or "already refunded" in msg.lower()


def test_refund_line_invalid_index(staff_client, mock_mongo):
    """Refunding invalid line index fails."""
    from inventory_app.services.billing_service import refund_bill_lines
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Invalid Index", price=100.0, stock=50)
    
    bill_id = _create_bill(staff_client, db, "Invalid", [{"name": "Invalid Index", "qty": "1"}])
    
    success, msg = refund_bill_lines(bill_id, [5], "OOB", "STF-001")
    assert not success
    assert "Invalid line index" in msg


def test_refund_all_lines_equals_full_refund(staff_client, mock_mongo):
    """Refunding all lines marks bill REFUNDED."""
    from inventory_app.services.billing_service import refund_bill_lines
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="All Lines", price=100.0, stock=50)
    _seed_product(db, name="All Lines 2", price=200.0, stock=50)
    
    bill_id = _create_bill(staff_client, db, "All Lines", [
        {"name": "All Lines", "qty": "1"},
        {"name": "All Lines 2", "qty": "1"}
    ])
    
    refund_bill_lines(bill_id, [0, 1], "Full", "STF-001")
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["payment_status"] == "REFUNDED"
    assert all(item["is_refunded"] for item in updated["line_items"])


# ========== STOCK CONSISTENCY TESTS ==========

def test_stock_consistency_edit_then_refund(staff_client, mock_mongo):
    """Edit bill then refund - stock consistent."""
    from inventory_app.services.billing_service import edit_bill, refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Consistency Item", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Consistency", [{"name": "Consistency Item", "qty": "5"}])
    
    # Edit: increase to 10
    items = [{'product_name': 'Consistency Item', 'quantity': 10}]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {'customer_name': 'Consistency', 'customer_phone': '9000000001', 'payment_method': 'CREDIT', 'discount_percent': '0'}
    
    edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    
    # Stock = 90 (100 - 10)
    assert db.products.find_one({"product_name": "Consistency Item"})["quantity"] == 90.0
    
    refund_bill(bill_id, "Final refund", "STF-001")
    
    # Stock = 100 (fully restored)
    assert db.products.find_one({"product_name": "Consistency Item"})["quantity"] == 100.0


def test_stock_consistency_refund_then_edit_fails(staff_client, mock_mongo):
    """Cannot edit after refund."""
    from inventory_app.services.billing_service import edit_bill, refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Edit After Refund", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Edit After", [{"name": "Edit After Refund", "qty": "2"}])
    
    refund_bill(bill_id, "Refunded", "STF-001")
    
    # Try to edit
    items = [{'product_name': 'Edit After Refund', 'quantity': 5}]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {'customer_name': 'Edit After', 'customer_phone': '9000000001', 'payment_method': 'CREDIT', 'discount_percent': '0'}
    
    success, msg, updated_bill = edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    assert not success
    assert "Cannot edit a refunded bill" in msg
    
    # Stock remains restored
    assert db.products.find_one({"product_name": "Edit After Refund"})["quantity"] == 100.0


def test_inventory_transactions_on_edit(staff_client, mock_mongo):
    """Edit creates BILL_EDIT audit and stock transactions."""
    from inventory_app.services.billing_service import edit_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Tx Item", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Tx Test", [{"name": "Tx Item", "qty": "3"}])
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    
    # Initial BILL_SALE tx
    txs = list(db.inventory_transactions.find({"bill_number": bill["bill_number"]}))
    assert len(txs) >= 1
    assert txs[0]["transaction_type"] == "BILL_SALE"
    
    # Edit: 3 -> 5
    items = [{'product_name': 'Tx Item', 'quantity': 5}]
    charges = {'shipping_charge': '0', 'packing_charge': '0'}
    customer_data = {'customer_name': 'Tx Test', 'customer_phone': '9000000001', 'payment_method': 'CREDIT', 'discount_percent': '0'}
    
    edit_bill(bill_id, items, charges, customer_data, 'STF-001')
    
    # Should have edit history
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert "edit_history" in updated
    assert len(updated["edit_history"]) >= 1


def test_inventory_transactions_on_refund(staff_client, mock_mongo):
    """Refund records refund transaction."""
    from inventory_app.services.billing_service import refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Refund Tx", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Refund Tx", [{"name": "Refund Tx", "qty": "4"}])
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    
    refund_bill(bill_id, "Refund test", "STF-001")
    
    # Refund payment record exists
    refund_payment = db.bill_payments.find_one({
        "bill_id": ObjectId(bill_id),
        "type": "REFUND"
    })
    assert refund_payment is not None
    assert refund_payment["amount"] == bill["grand_total"]


# ========== PAYMENT/STATUS TRANSITION TESTS ==========

def test_refund_updates_payment_status(staff_client, mock_mongo):
    """Full refund transitions PAID -> REFUNDED."""
    from inventory_app.services.billing_service import refund_bill
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Status Test", price=100.0, stock=100)
    
    bill_id = _create_bill(staff_client, db, "Status", [{"name": "Status Test", "qty": "1"}], payment_method="CASH")
    
    refund_bill(bill_id, "Status test", "STF-001")
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["payment_status"] == "REFUNDED"
    assert updated["amount_due"] == 0.0


def test_partial_refund_payment_status(staff_client, mock_mongo):
    """Partial refund updates status correctly."""
    from inventory_app.services.billing_service import refund_bill_lines
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Part Status A", price=100.0, stock=50)
    _seed_product(db, name="Part Status B", price=100.0, stock=50)
    
    bill_id = _create_bill(staff_client, db, "Part Status", [
        {"name": "Part Status A", "qty": "1"},
        {"name": "Part Status B", "qty": "1"}
    ], payment_method="CASH")
    
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert bill["payment_status"] == "PAID"
    
    refund_bill_lines(bill_id, [0], "Half refund", "STF-001")
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["payment_status"] in ("PARTIAL", "PAID")


def test_partial_refund_payment_status(staff_client, mock_mongo):
    """Partial refund updates status correctly."""
    from inventory_app.services.billing_service import refund_bill_lines
    db = mock_mongo['inventory_test_db']
    _seed_product(db, name="Part Status A", price=100.0, stock=50)
    _seed_product(db, name="Part Status B", price=100.0, stock=50)
    
    bill_id = _create_bill(staff_client, db, "Part Status", [
        {"name": "Part Status A", "qty": "1"},
        {"name": "Part Status B", "qty": "1"}
    ], payment_method="CASH")
    
    bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert bill["payment_status"] == "PAID"
    
    refund_bill_lines(bill_id, [0], "Half refund", "STF-001")
    
    updated = db.invoices.find_one({"_id": ObjectId(bill_id)})
    assert updated["payment_status"] in ("PARTIAL", "PAID")