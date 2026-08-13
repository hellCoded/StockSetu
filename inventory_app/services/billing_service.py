import re
from datetime import datetime, timezone
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from inventory_app.database import get_db
from inventory_app.services.product_service import get_product_by_name
from inventory_app.services.audit_service import log_audit

def _round2(value: float) -> float:
    return round(value + 1e-9, 2)

def _financial_year(dt: datetime) -> str:
    """Returns Indian financial year label e.g. 2026-27 (April–March)."""
    year = dt.year
    if dt.month >= 4:
        start, end = year, year + 1
    else:
        start, end = year - 1, year
    return f"{start}-{str(end)[-2:]}"

def _generate_bill_number(db, now: datetime) -> str:
    """Atomically generates a sequential invoice number in Indian FY format: INV/2026-27/0001."""
    counter = db.bill_counters.find_one_and_update(
        {"_id": "invoice_seq"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    seq = counter.get("seq", 1)
    return f"INV/{_financial_year(now)}/{seq:04d}"

def _validate_gstin(gstin: str) -> bool:
    """Validates Indian GSTIN format: 2 digit state + 10 PAN + entity + Z + checksum."""
    return bool(re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}Z[0-9A-Z]{1}$', gstin.upper()))

def _deduct_stock(db, canonical_name: str, quantity: float, now: datetime, performed_by: str) -> tuple[bool, str, str]:
    """Atomically deducts stock for a sale item. Records BILL_SALE transaction."""
    product = get_product_by_name(canonical_name)
    if not product:
        return False, f"Product '{canonical_name}' not found.", ""
    if not product.get("is_active", True):
        return False, f"Product '{canonical_name}' is inactive and cannot be billed.", ""

    prev_qty = float(product.get("quantity", 0))
    if prev_qty < quantity:
        return False, f"Insufficient stock for '{canonical_name}'. Available: {prev_qty}, Requested: {quantity}.", ""

    res = db.products.update_one(
        {"product_name": canonical_name, "quantity": {"$gte": quantity}},
        {"$inc": {"quantity": -quantity}, "$set": {"updated_at": now}}
    )
    if res.modified_count == 0:
        return False, f"Stock deduction failed for '{canonical_name}' (insufficient available inventory).", ""

    tx_res = db.inventory_transactions.insert_one({
        "product_name": canonical_name,
        "transaction_type": "BILL_SALE",
        "quantity": quantity,
        "previous_quantity": prev_qty,
        "new_quantity": _round2(prev_qty - quantity),
        "reason": f"Sale via bill (performed by {performed_by})",
        "performed_by": performed_by,
        "created_at": now
    })
    return True, "", str(tx_res.inserted_id)

def create_bill(customer_data: dict, items: list, performed_by: str) -> tuple[bool, str, dict]:
    """
    Creates a GST invoice from sale items.
    - Validates customer and item data
    - Computes taxable value, CGST/SGST split, and grand total per item
    - Atomically deducts stock (refunds everything and rolls back transactions if any line fails)
    - Generates sequential Indian financial-year invoice number
    """
    db = get_db()

    customer_name = (customer_data.get('customer_name') or '').strip()
    if not customer_name:
        return False, "Customer name is required.", {}
    if len(customer_name) > 120:
        return False, "Customer name cannot exceed 120 characters.", {}

    customer_phone = (customer_data.get('customer_phone') or '').strip()
    if customer_phone and not re.match(r'^[0-9+\- ]{7,15}$', customer_phone):
        return False, "Phone number is invalid.", {}

    customer_gstin = (customer_data.get('customer_gstin') or '').strip().upper()
    if customer_gstin and not _validate_gstin(customer_gstin):
        return False, "GSTIN is invalid. Format: 15-character (e.g., 27ABCDE1234F1Z5).", {}

    payment_method = (customer_data.get('payment_method') or 'CASH').strip().upper()
    if payment_method not in ('CASH', 'UPI', 'CARD', 'CREDIT'):
        return False, "Payment method must be CASH, UPI, CARD or CREDIT.", {}

    if not items or not isinstance(items, list):
        return False, "At least one item is required to create a bill.", {}

    now = datetime.now(timezone.utc)
    bill_items = []
    subtotal = 0.0
    cgst_total = 0.0
    sgst_total = 0.0
    gst_total = 0.0

    for raw_item in items:
        name = re.sub(r'\s+', ' ', (raw_item.get('product_name') or '').strip())
        if not name:
            return False, "Each bill item must have a product name.", {}

        try:
            quantity = float(raw_item.get('quantity', 0))
        except (ValueError, TypeError):
            return False, f"Quantity for '{name}' must be a valid number.", {}
        if quantity <= 0:
            return False, f"Quantity for '{name}' must be greater than zero.", {}

        product = get_product_by_name(name)
        if not product:
            return False, f"Product '{name}' not found.", {}
        if not product.get("is_active", True):
            return False, f"Product '{name}' is inactive and cannot be billed.", {}

        canonical_name = product["product_name"]
        unit_price = _round2(float(product.get("price", 0)))
        gst_rate = float(product.get("gst_rate", 0) or 0)
        taxable = _round2(unit_price * quantity)
        gst_amount = _round2(taxable * gst_rate / 100)
        cgst = _round2(gst_amount / 2)
        sgst = _round2(gst_amount - cgst)
        line_total = _round2(taxable + cgst + sgst)

        bill_items.append({
            "product_name": canonical_name,
            "hsn_code": product.get("hsn_code", ''),
            "quantity": quantity,
            "unit_price": unit_price,
            "gst_rate": gst_rate,
            "taxable": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "gst_amount": gst_amount,
            "line_total": line_total
        })
        subtotal = _round2(subtotal + taxable)
        cgst_total = _round2(cgst_total + cgst)
        sgst_total = _round2(sgst_total + sgst)
        gst_total = _round2(gst_total + gst_amount)

    try:
        discount_percent = float(customer_data.get('discount_percent', 0) or 0)
    except (ValueError, TypeError):
        discount_percent = 0.0
    discount_percent = max(0.0, min(100.0, discount_percent))
    discount_amount = _round2(subtotal * discount_percent / 100)

    grand_total = _round2((subtotal - discount_amount) + gst_total)
    bill_number = _generate_bill_number(db, now)

    # Deduct stock atomically; refund everything and delete transaction logs if any line fails
    deducted = []
    inserted_tx_ids = []
    for item in bill_items:
        success, err, tx_id = _deduct_stock(db, item["product_name"], item["quantity"], now, performed_by)
        if not success:
            for refund in deducted:
                db.products.update_one(
                    {"product_name": refund["product_name"]},
                    {"$inc": {"quantity": refund["quantity"]}}
                )
            if inserted_tx_ids:
                db.inventory_transactions.delete_many({"_id": {"$in": [ObjectId(t) for t in inserted_tx_ids if ObjectId.is_valid(t)]}})
            return False, err, {}

        deducted.append({"product_name": item["product_name"], "quantity": item["quantity"]})
        if tx_id:
            inserted_tx_ids.append(tx_id)

    bill_doc = {
        "bill_number": bill_number,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_gstin": customer_gstin,
        "payment_method": payment_method,
        "payment_status": "PAID",
        "line_items": bill_items,
        "subtotal": subtotal,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "cgst_total": cgst_total,
        "sgst_total": sgst_total,
        "gst_total": gst_total,
        "grand_total": grand_total,
        "created_by": performed_by,
        "created_at": now
    }

    try:
        res = db.invoices.insert_one(bill_doc)
        bill_doc["_id"] = str(res.inserted_id)
        log_audit("BILL_CREATE", performed_by, bill_number, {
            "grand_total": grand_total,
            "items": len(bill_items),
            "customer": customer_name
        })
        return True, f"Bill {bill_number} created successfully.", bill_doc
    except Exception as e:
        for refund in deducted:
            db.products.update_one(
                {"product_name": refund["product_name"]},
                {"$inc": {"quantity": refund["quantity"]}}
            )
        if inserted_tx_ids:
            db.inventory_transactions.delete_many({"_id": {"$in": [ObjectId(t) for t in inserted_tx_ids if ObjectId.is_valid(t)]}})
        return False, f"Failed to create bill: {str(e)}", {}

def get_bill_by_id(bill_id: str) -> dict:
    """Retrieves a bill by its MongoDB ObjectId string."""
    db = get_db()
    try:
        bill = db.invoices.find_one({"_id": ObjectId(bill_id)})
    except Exception:
        bill = None
    if bill:
        bill["_id"] = str(bill["_id"])
    return bill

def get_bill_by_number(bill_number: str) -> dict:
    """Retrieves a bill by its invoice number."""
    db = get_db()
    bill = db.invoices.find_one({"bill_number": bill_number.strip().upper()})
    if bill:
        bill["_id"] = str(bill["_id"])
    return bill

def get_bills(search: str = "", limit: int = 100) -> list:
    """Lists invoices, newest first, with optional bill number/customer search."""
    db = get_db()
    query = {}
    search = search.strip()
    if search:
        escaped = re.escape(search)
        query["$or"] = [
            {"bill_number": {"$regex": escaped, "$options": "i"}},
            {"customer_name": {"$regex": escaped, "$options": "i"}}
        ]
    projection = {
        "bill_number": 1,
        "customer_name": 1,
        "customer_phone": 1,
        "payment_method": 1,
        "payment_status": 1,
        "grand_total": 1,
        "created_at": 1,
        "line_items": 1
    }
    bills = list(db.invoices.find(query, projection).sort("created_at", -1).limit(limit))
    for b in bills:
        b["_id"] = str(b["_id"])
    return bills

def get_billing_summary() -> dict:
    """
    Returns billing metrics for the dashboard:
    - Total invoices count
    - Today's invoice count and sales value
    - All-time sales value
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_bills = list(db.invoices.find({"created_at": {"$gte": start_of_today}}, {"grand_total": 1}))
    total_bills = db.invoices.count_documents({})

    today_sales = sum(float(b.get("grand_total", 0) or 0) for b in today_bills)

    all_bills = list(db.invoices.find({}, {"grand_total": 1}))
    total_sales = sum(float(b.get("grand_total", 0) or 0) for b in all_bills)

    return {
        "total_bills": total_bills,
        "today_bills": len(today_bills),
        "today_sales": today_sales,
        "total_sales": total_sales
    }

def refund_bill(bill_id: str, reason: str, performed_by: str) -> tuple[bool, str]:
    """Cancels/refunds an invoice, restores stock for all items, and records transaction/audit logs."""
    db = get_db()
    bill = get_bill_by_id(bill_id)
    if not bill:
        return False, "Bill not found."

    if bill.get("payment_status") == "REFUNDED":
        return False, "Bill has already been refunded."

    now = datetime.now(timezone.utc)
    reason_clean = (reason or "Customer refund").strip()

    # Restore stock for each item in the bill
    for item in bill.get("line_items", []):
        prod_name = item.get("product_name")
        qty = float(item.get("quantity", 0))
        if prod_name and qty > 0:
            db.products.update_one(
                {"product_name": prod_name},
                {"$inc": {"quantity": qty}, "$set": {"updated_at": now}}
            )
            db.inventory_transactions.insert_one({
                "product_name": prod_name,
                "transaction_type": "BILL_REFUND",
                "quantity": qty,
                "reason": f"Refund for bill {bill.get('bill_number')}: {reason_clean}",
                "performed_by": performed_by,
                "created_at": now
            })

    db.invoices.update_one(
        {"_id": ObjectId(bill_id)},
        {"$set": {
            "payment_status": "REFUNDED",
            "refunded_at": now,
            "refunded_by": performed_by,
            "refund_reason": reason_clean
        }}
    )
    log_audit("BILL_REFUND", performed_by, bill.get("bill_number"), {"reason": reason_clean})
    return True, f"Bill {bill.get('bill_number')} refunded successfully and inventory stock restored."