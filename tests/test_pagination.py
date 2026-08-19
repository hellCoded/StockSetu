import pytest
from inventory_app.utils.pagination import Pagination


def test_pagination_math_calculations():
    p = Pagination(page=1, per_page=10, total=45)
    assert p.page == 1
    assert p.per_page == 10
    assert p.total == 45
    assert p.pages == 5
    assert p.start_item == 1
    assert p.end_item == 10
    assert p.has_prev is False
    assert p.has_next is True
    assert p.prev_num is None
    assert p.next_num == 2


def test_pagination_middle_page():
    p = Pagination(page=3, per_page=10, total=45)
    assert p.page == 3
    assert p.start_item == 21
    assert p.end_item == 30
    assert p.has_prev is True
    assert p.has_next is True
    assert p.prev_num == 2
    assert p.next_num == 4


def test_pagination_last_page():
    p = Pagination(page=5, per_page=10, total=45)
    assert p.page == 5
    assert p.start_item == 41
    assert p.end_item == 45
    assert p.has_prev is True
    assert p.has_next is False


def test_pagination_clamping_out_of_bounds():
    # Page requested exceeds total pages -> clamp to last page
    p = Pagination(page=99, per_page=10, total=25)
    assert p.page == 3
    assert p.pages == 3

    # Negative page -> clamp to 1
    p2 = Pagination(page=-5, per_page=10, total=25)
    assert p2.page == 1

    # Zero total items
    p3 = Pagination(page=1, per_page=10, total=0)
    assert p3.total == 0
    assert p3.pages == 1
    assert p3.start_item == 0
    assert p3.end_item == 0


def test_pagination_iter_pages():
    p = Pagination(page=5, per_page=10, total=100)  # 10 pages total
    pages = list(p.iter_pages(left_edge=1, left_current=2, right_current=2, right_edge=1))
    # Expected: 1, None, 3, 4, 5, 6, 7, None, 10
    assert 1 in pages
    assert 5 in pages
    assert 10 in pages
    assert None in pages


def test_pagination_url_generation():
    p = Pagination(page=2, per_page=15, total=50)
    url = p.url_for_page(3, {'q': 'Steel', 'category': 'Hardware'})
    assert 'page=3' in url
    assert 'per_page=15' in url
    assert 'q=Steel' in url
    assert 'category=Hardware' in url


# ── Integration tests for routes with pagination ─────────────────────

def test_products_pagination_route(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    # Seed 12 products
    for i in range(12):
        name = f"Paginated Item {i:02d}"
        db.products.insert_one({
            "product_name": name,
            "product_name_lower": name.lower(),
            "category": "Tools",
            "quantity": 10,
            "minimum_stock": 5,
            "price": 100.0,
            "gst_rate": 18,
            "unit": "pcs",
            "is_active": True,
        })

    resp = staff_client.get('/products?page=1&per_page=5')
    assert resp.status_code == 200
    assert b"Showing" in resp.data
    assert b"of" in resp.data


def test_billing_pagination_route(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    for i in range(8):
        db.invoices.insert_one({
            "bill_number": f"INV/2026-27/{i+1:04d}",
            "customer_name": f"Customer {i}",
            "payment_method": "CASH",
            "payment_status": "PAID",
            "grand_total": 500.0,
            "amount_paid": 500.0,
            "amount_due": 0.0,
            "created_at": "2026-08-18T10:00:00",
            "line_items": [],
        })

    resp = staff_client.get('/billing/bills?page=1&per_page=4')
    assert resp.status_code == 200
    assert b"Showing" in resp.data
    assert b"Next" in resp.data


def test_transactions_pagination_route(staff_client, mock_mongo):
    db = mock_mongo['inventory_test_db']
    for i in range(6):
        db.inventory_transactions.insert_one({
            "product_name": "Test Item",
            "transaction_type": "STOCK_IN",
            "quantity": 5,
            "previous_quantity": 0,
            "new_quantity": 5,
            "reason": f"Batch {i}",
            "performed_by": "staff",
            "created_at": "2026-08-18T10:00:00",
        })

    resp = staff_client.get('/transactions?page=1&per_page=3')
    assert resp.status_code == 200
    assert b"Showing" in resp.data


def test_users_pagination_route(admin_client, mock_mongo):
    resp = admin_client.get('/users?page=1&per_page=5')
    assert resp.status_code == 200
    assert b"Showing" in resp.data
