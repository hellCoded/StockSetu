import pytest
from datetime import datetime, timezone
from inventory_app import cache_flush
from inventory_app.services.billing_service import get_sales_analytics


def test_sales_analytics_empty_db(app, mock_mongo):
    db = mock_mongo['inventory_test_db']
    db.invoices.delete_many({})
    cache_flush()
    analytics = get_sales_analytics()
    assert analytics["kpi"]["total_sales"] == 0
    assert analytics["kpi"]["total_bills"] == 0
    # Every registered user is in the leaderboard with 0 sales
    assert len(analytics["staff_leaderboard"]) >= 1
    for s in analytics["staff_leaderboard"]:
        assert s["total_sales"] == 0.0
    assert analytics["top_products"] == []


def test_sales_analytics_with_invoices(app, mock_mongo):
    db = mock_mongo['inventory_test_db']
    db.invoices.delete_many({})
    cache_flush()
    now = datetime.now(timezone.utc)

    # Insert sample invoices for two cashiers
    db.invoices.insert_many([
        {
            "bill_number": "INV/2026-27/0001",
            "customer_name": "Customer A",
            "payment_method": "CASH",
            "payment_status": "PAID",
            "grand_total": 1000.0,
            "amount_paid": 1000.0,
            "amount_due": 0.0,
            "total_cgst": 90.0,
            "total_sgst": 90.0,
            "created_by": "alice",
            "created_at": now,
            "line_items": [
                {"product_name": "Product 1", "quantity": 2, "line_total": 500.0, "is_refunded": False},
                {"product_name": "Product 2", "quantity": 1, "line_total": 500.0, "is_refunded": False}
            ]
        },
        {
            "bill_number": "INV/2026-27/0002",
            "customer_name": "Customer B",
            "payment_method": "UPI",
            "payment_status": "PAID",
            "grand_total": 2000.0,
            "amount_paid": 2000.0,
            "amount_due": 0.0,
            "total_cgst": 180.0,
            "total_sgst": 180.0,
            "created_by": "bob",
            "created_at": now,
            "line_items": [
                {"product_name": "Product 1", "quantity": 4, "line_total": 2000.0, "is_refunded": False}
            ]
        }
    ])

    analytics = get_sales_analytics(date_preset="30d")
    kpi = analytics["kpi"]

    assert kpi["total_sales"] == 3000.0
    assert kpi["total_bills"] == 2
    assert kpi["avg_bill_value"] == 1500.0
    assert kpi["total_tax"] == 540.0

    # Verify staff leaderboard ranks top sellers first
    staff = analytics["staff_leaderboard"]
    assert staff[0]["cashier"] == "bob"
    assert staff[0]["total_sales"] == 2000.0
    assert staff[0]["upi_sales"] == 2000.0
    assert staff[1]["cashier"] == "alice"
    assert staff[1]["total_sales"] == 1000.0
    assert staff[1]["cash_sales"] == 1000.0
    # Other registered staff members are also enlisted with 0 sales
    assert len(staff) >= 2

    # Top products: Product 1 has 6 units sold across 2 invoices
    top_p = analytics["top_products"]
    assert len(top_p) == 2
    assert top_p[0]["product_name"] == "Product 1"
    assert top_p[0]["quantity_sold"] == 6.0


def test_sales_analytics_route_renders(staff_client, mock_mongo):
    resp = staff_client.get('/billing/sales')
    assert resp.status_code == 200
    assert b"Sales Analytics" in resp.data
    assert b"Staff / Cashier Performance Leaderboard" in resp.data
    assert b"Top Selling Products" in resp.data


def test_sales_export_route(staff_client, mock_mongo):
    resp = staff_client.get('/billing/sales/export?range=30d')
    assert resp.status_code == 200
    assert resp.content_type == "text/csv; charset=utf-8" or "text/csv" in resp.content_type
    assert b"STOCKSETU SALES ANALYTICS REPORT" in resp.data
    assert b"KEY PERFORMANCE INDICATORS" in resp.data
