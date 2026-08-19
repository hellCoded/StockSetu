from inventory_app.services.billing_service import create_bill, refund_bill
from inventory_app.services.product_service import create_product, get_product_by_name
from inventory_app.services.inventory_service import stock_in

def test_billing_discount_and_refund(app, mock_mongo):
    with app.app_context():
        # Create product (qty=5 hardcoded), then stock in to get enough for billing
        create_product({
            "product_name": "Steel Rod 10mm",
            "category": "Hardware",
            "unit": "pcs",
            "minimum_stock": 5,
            "price": 100.0,
            "gst_rate": 18.0
        }, "admin")

        stock_in("Steel Rod 10mm", 45.0, "Test restock", performed_by="admin")
        prod = get_product_by_name("Steel Rod 10mm")
        assert float(prod["quantity"]) == 50.0

        customer_data = {
            "customer_name": "Test Customer",
            "customer_phone": "9876543210",
            "payment_method": "CASH",
            "discount_percent": 10.0
        }
        items = [{"product_name": "Steel Rod 10mm", "quantity": 10.0}]

        success, msg, bill = create_bill(customer_data, items, performed_by="admin")
        assert success
        assert bill["discount_percent"] == 10.0
        assert bill["discount_amount"] == 100.0  # 10% of 1000 subtotal
        # Subtotal: 1000, Tax: 180, Discount: 100 => Grand: 1080
        assert bill["grand_total"] == 1080.0

        # Verify stock decreased to 40
        prod = get_product_by_name("Steel Rod 10mm")
        assert float(prod["quantity"]) == 40.0

        # Refund bill
        ref_ok, ref_msg = refund_bill(bill["_id"], "Customer return", "admin")
        assert ref_ok

        # Verify stock restored to 50
        prod_after = get_product_by_name("Steel Rod 10mm")
        assert float(prod_after["quantity"]) == 50.0

def test_gzip_compression(client):
    """Verifies that requests with Accept-Encoding: gzip receive compressed responses."""
    resp = client.get('/static/css/bundle.css', headers={'Accept-Encoding': 'gzip'})
    assert resp.status_code == 200
    assert resp.headers.get('Content-Encoding') == 'gzip'

def test_user_session_caching(app, mock_mongo):
    """Verifies that get_user_by_id caches results and invalidation clears them."""
    from inventory_app.services.auth_service import register_user, get_user_by_id, toggle_user_active
    with app.app_context():
        ok, msg, user = register_user(employee_id="perf_user", email="perf@test.com", password="Password@123", role="staff")
        assert ok
        uid = str(user["_id"])

        # First fetch (populates cache)
        u1 = get_user_by_id(uid)
        assert u1 is not None
        assert u1["is_active"] is True

        # Toggle active status (must invalidate cache)
        toggle_ok, toggle_msg, new_status = toggle_user_active(uid)
        assert toggle_ok
        assert new_status is False

        # Fresh read must reflect updated state
        u2 = get_user_by_id(uid)
        assert u2 is not None
        assert u2["is_active"] is False



