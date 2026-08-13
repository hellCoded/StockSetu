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
            "minimum_stock": 5.0,
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


