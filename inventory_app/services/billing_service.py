import math
import re
import time
from datetime import datetime, timezone
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from inventory_app.database import get_db
from inventory_app.services.product_service import get_product_by_name, invalidate_product_cache
from inventory_app.services.audit_service import log_audit
from inventory_app import cache_get, cache_set

# ── Billing summary cache (global,60-second TTL) ──
_BILLING_SUMMARY_TTL = 60


def _cached_billing_summary():
    """Returns cached billing summary, refreshing every30 seconds. Uses global cache (Upstash on Vercel)."""
    cache_key = "billing:summary"
    cached = cache_get(cache_key)
    if cached:
        import json
        try:
            return json.loads(cached)
        except Exception:
            pass
    data = get_billing_summary()
    import json
    cache_set(cache_key, json.dumps(data, default=str), ttl=_BILLING_SUMMARY_TTL)
    return data


def _round2(value: float) -> float:
    return round(value + 1e-9, 2)


def _financial_year(dt: datetime) -> str:
    """Returns Indian financial year label e.g. 2026-27 (April-March)."""
    year = dt.year
    if dt.month >= 4:
        start, end = year, year + 1
    else:
        start, end = year - 1, year
    return f"{start}-{str(end)[-2:]}"


def _generate_bill_number(db, now: datetime) -> str:
    """Atomically generates a sequential invoice number in Indian FY format."""
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


# ──────────────────────────────────────────────────────────────────────
# Pure computation (no DB)
# ──────────────────────────────────────────────────────────────────────

def compute_line(unit_price: float, quantity: float, gst_rate: float,
                 line_discount_percent: float = 0.0, is_free_override: bool = False):
    """
    Pure function: computes one line item's tax/discount/total.
    Returns (ok, msg, computed_dict).
    """
    if not math.isfinite(quantity) or not math.isfinite(unit_price) or not math.isfinite(gst_rate):
        return False, "Invalid numeric values in line item.", {}
    if quantity <= 0:
        return False, "Quantity must be greater than zero.", {}
    if unit_price < 0:
        return False, "Unit price cannot be negative.", {}

    line_discount_percent = max(0.0, min(100.0, float(line_discount_percent)))
    gst_rate = max(0.0, min(28.0, float(gst_rate)))

    raw_taxable = _round2(unit_price * quantity)
    line_discount_amount = _round2(raw_taxable * line_discount_percent / 100)
    taxable = _round2(raw_taxable - line_discount_amount)

    is_free = bool(is_free_override or (line_discount_percent >= 100.0 and quantity > 0))

    gst_amount = _round2(taxable * gst_rate / 100)
    cgst = _round2(gst_amount / 2)
    sgst = _round2(gst_amount - cgst)
    line_total = _round2(taxable + gst_amount)

    return True, "", {
        "raw_taxable": raw_taxable,
        "line_discount_percent": line_discount_percent,
        "line_discount_amount": line_discount_amount,
        "taxable": taxable,
        "gst_rate": gst_rate,
        "gst_amount": gst_amount,
        "cgst": cgst,
        "sgst": sgst,
        "line_total": line_total,
        "is_free": is_free,
    }


def compute_bill(customer_data: dict, items_with_products: list,
                 charges: dict = None, payment_splits: list = None):
    """
    Pure function: validates customer + item data, computes full bill totals.
    Each element in items_with_products must contain: product_name, product (dict), quantity.
    Optional per-item keys: line_discount_percent, is_free.
    Returns (ok, msg, computed_dict).
    """
    customer_name = re.sub(r'\s+', ' ', (customer_data.get('customer_name') or '').strip())
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

    if not items_with_products or not isinstance(items_with_products, list):
        return False, "At least one item is required to create a bill.", {}

    # ── Per-line computation ──
    bill_items = []
    subtotal = 0.0
    cgst_total = 0.0
    sgst_total = 0.0
    gst_total = 0.0

    for raw in items_with_products:
        product = raw.get('product')
        if not product:
            return False, f"Product lookup missing for '{raw.get('product_name', '?')}'.", {}

        canonical_name = product.get('product_name', '')
        quantity = float(raw.get('quantity', 0))
        line_discount = float(raw.get('line_discount_percent', 0) or 0)
        is_free_override = bool(raw.get('is_free', False))

        if not product.get("is_active", True):
            return False, f"Product '{canonical_name}' is inactive and cannot be billed.", {}

        unit_price = _round2(float(product.get("price", 0)))
        gst_rate = float(product.get("gst_rate", 0) or 0)

        ok, msg, computed = compute_line(unit_price, quantity, gst_rate, line_discount, is_free_override)
        if not ok:
            return False, f"{msg} (product: '{canonical_name}')", {}

        bill_items.append({
            "product_name": canonical_name,
            "hsn_code": product.get("hsn_code", ''),
            "quantity": quantity,
            "unit_price": unit_price,
            "line_discount_percent": computed["line_discount_percent"],
            "line_discount_amount": computed["line_discount_amount"],
            "raw_taxable": computed["raw_taxable"],
            "taxable": computed["taxable"],
            "gst_rate": computed["gst_rate"],
            "gst_amount": computed["gst_amount"],
            "cgst": computed["cgst"],
            "sgst": computed["sgst"],
            "line_total": computed["line_total"],
            "is_free": computed["is_free"],
            "is_refunded": False,
            "refund_quantity": 0.0,
        })
        subtotal = _round2(subtotal + computed["raw_taxable"])
        cgst_total = _round2(cgst_total + computed["cgst"])
        sgst_total = _round2(sgst_total + computed["sgst"])
        gst_total = _round2(gst_total + computed["gst_amount"])

    total_line_discount = _round2(sum(i["line_discount_amount"] for i in bill_items))
    taxable_after_line_discount = _round2(subtotal - total_line_discount)
    free_total = _round2(sum(i["line_total"] for i in bill_items if i["is_free"]))

    # ── Bill-level discount ──
    try:
        discount_percent = float(customer_data.get('discount_percent', 0) or 0)
    except (ValueError, TypeError):
        discount_percent = 0.0
    discount_percent = max(0.0, min(100.0, discount_percent))
    discount_amount = _round2(taxable_after_line_discount * discount_percent / 100)
    taxable_final = _round2(taxable_after_line_discount - discount_amount)

    # ── Extra charges ──
    charges = charges or {}
    try:
        shipping_charge = _round2(float(charges.get('shipping_charge', 0) or 0))
    except (ValueError, TypeError):
        shipping_charge = 0.0
    try:
        packing_charge = _round2(float(charges.get('packing_charge', 0) or 0))
    except (ValueError, TypeError):
        packing_charge = 0.0
    charges_total = _round2(shipping_charge + packing_charge)

    # ── Grand total before round-off ──
    grand_raw = _round2(taxable_final + gst_total + charges_total)
    round_off = _round2(round(grand_raw) - grand_raw)
    grand_total = _round2(grand_raw + round_off)

    # ── Payment splits ──
    if payment_splits and isinstance(payment_splits, list) and len(payment_splits) > 0:
        total_paid = 0.0
        for s in payment_splits:
            try:
                total_paid = _round2(total_paid + float(s.get('amount', 0)))
            except (ValueError, TypeError):
                pass
        if total_paid < 0:
            return False, "Total payment cannot be negative.", {}
        if total_paid > grand_total:
            return False, f"Total payment ({total_paid}) exceeds grand total ({grand_total}).", {}
    else:
        payment_splits = []
        if payment_method == 'CREDIT':
            total_paid = 0.0
        else:
            total_paid = grand_total

    # ── Due date for credit ──
    due_date = customer_data.get('due_date', None)
    if payment_method == 'CREDIT' and total_paid < grand_total and not due_date:
        return False, "Due date is required for credit sales.", {}

    # ── Payment status ──
    if grand_total <= 0:
        payment_status = 'PAID'
        total_paid = grand_total
    elif total_paid >= grand_total:
        payment_status = 'PAID'
        total_paid = grand_total
    elif total_paid > 0:
        payment_status = 'PARTIAL'
    else:
        payment_status = 'DUE'

    amount_due = _round2(grand_total - total_paid)

    return True, "", {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_gstin": customer_gstin,
        "payment_method": payment_method,
        "payment_status": payment_status,
        "line_items": bill_items,
        "subtotal": subtotal,
        "total_line_discount": total_line_discount,
        "cgst_total": cgst_total,
        "sgst_total": sgst_total,
        "gst_total": gst_total,
        "free_total": free_total,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "shipping_charge": shipping_charge,
        "packing_charge": packing_charge,
        "charges_total": charges_total,
        "round_off": round_off,
        "grand_total": grand_total,
        "amount_paid": total_paid,
        "amount_due": amount_due,
        "due_date": due_date,
        "payment_splits": payment_splits,
    }


# ──────────────────────────────────────────────────────────────────────
# Stock helpers
# ──────────────────────────────────────────────────────────────────────

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
    invalidate_product_cache(canonical_name)
    return True, "", str(tx_res.inserted_id)


def _restore_stock(db, canonical_name: str, quantity: float, now: datetime, performed_by: str, reason: str = ""):
    """Restores stock for a refund item. Records BILL_REFUND transaction."""
    product = get_product_by_name(canonical_name)
    prev_qty = float(product.get("quantity", 0)) if product else 0
    db.products.update_one(
        {"product_name": canonical_name},
        {"$inc": {"quantity": quantity}, "$set": {"updated_at": now}}
    )
    db.inventory_transactions.insert_one({
        "product_name": canonical_name,
        "transaction_type": "BILL_REFUND",
        "quantity": quantity,
        "previous_quantity": prev_qty,
        "new_quantity": _round2(prev_qty + quantity),
        "reason": reason,
        "performed_by": performed_by,
        "created_at": now
    })
    invalidate_product_cache(canonical_name)


# ──────────────────────────────────────────────────────────────────────
# Audit helpers
# ──────────────────────────────────────────────────────────────────────

def _bill_snapshot(bill_doc: dict) -> dict:
    """Returns an immutable snapshot of the bill for audit records."""
    return {
        "bill_number": bill_doc.get("bill_number"),
        "line_items": [dict(l) for l in bill_doc.get("line_items", [])],
        "subtotal": bill_doc.get("subtotal"),
        "total_line_discount": bill_doc.get("total_line_discount", 0),
        "discount_percent": bill_doc.get("discount_percent", 0),
        "discount_amount": bill_doc.get("discount_amount", 0),
        "cgst_total": bill_doc.get("cgst_total"),
        "sgst_total": bill_doc.get("sgst_total"),
        "gst_total": bill_doc.get("gst_total"),
        "shipping_charge": bill_doc.get("shipping_charge", 0),
        "packing_charge": bill_doc.get("packing_charge", 0),
        "round_off": bill_doc.get("round_off", 0),
        "grand_total": bill_doc.get("grand_total"),
        "amount_paid": bill_doc.get("amount_paid", 0),
        "payment_method": bill_doc.get("payment_method"),
        "payment_status": bill_doc.get("payment_status"),
        "customer_name": bill_doc.get("customer_name"),
    }


def _log_rejected_attempt(performed_by: str, items: list, reason: str, customer_data: dict = None):
    """Logs a rejected bill creation attempt for audit."""
    log_audit("BILL_CREATE_REJECTED", performed_by, None, {
        "items": [{"product_name": i.get("product_name"), "quantity": i.get("quantity")} for i in (items or [])],
        "reason": reason,
        "customer": (customer_data or {}).get("customer_name", ""),
    })


# ──────────────────────────────────────────────────────────────────────
# Main: create_bill
# ──────────────────────────────────────────────────────────────────────

def create_bill(customer_data: dict, items: list, performed_by: str,
                charges: dict = None, payment_splits: list = None) -> tuple[bool, str, dict]:
    """
    Creates a GST invoice from sale items.
    - Resolves products from DB
    - Computes taxable, GST, discounts, charges, round-off via compute_bill
    - Atomically deducts stock (full rollback on any line failure)
    - Writes immutable audit snapshot and bill_payments records
    """
    db = get_db()

    if not items or not isinstance(items, list):
        _log_rejected_attempt(performed_by, items, "No items provided", customer_data)
        return False, "At least one item is required to create a bill.", {}

    # ── Resolve products ──
    items_with_products = []
    for raw_item in items:
        name = re.sub(r'\s+', ' ', (raw_item.get('product_name') or '').strip())
        if not name:
            _log_rejected_attempt(performed_by, items, "Empty product name in line item", customer_data)
            return False, "Each bill item must have a product name.", {}

        try:
            quantity = float(raw_item.get('quantity', 0))
        except (ValueError, TypeError):
            _log_rejected_attempt(performed_by, items, f"Invalid quantity for '{name}'", customer_data)
            return False, f"Quantity for '{name}' must be a valid number.", {}
        if quantity <= 0:
            _log_rejected_attempt(performed_by, items, f"Non-positive quantity ({quantity}) for '{name}'", customer_data)
            return False, f"Quantity for '{name}' must be greater than zero.", {}

        product = get_product_by_name(name)
        if not product:
            _log_rejected_attempt(performed_by, items, f"Product '{name}' not found", customer_data)
            return False, f"Product '{name}' not found.", {}

        items_with_products.append({
            "product_name": product["product_name"],
            "product": product,
            "quantity": quantity,
            "line_discount_percent": float(raw_item.get('line_discount_percent', 0) or 0),
            "is_free": bool(raw_item.get('is_free', False)),
        })

    # ── Compute bill ──
    ok, msg, computed = compute_bill(customer_data, items_with_products, charges, payment_splits)
    if not ok:
        _log_rejected_attempt(performed_by, items, msg, customer_data)
        return False, msg, {}

    now = datetime.now(timezone.utc)
    bill_number = _generate_bill_number(db, now)

    # ── Deduct stock atomically (rollback on failure) ──
    deducted = []
    inserted_tx_ids = []
    for item in computed["line_items"]:
        success, err, tx_id = _deduct_stock(db, item["product_name"], item["quantity"], now, performed_by)
        if not success:
            for ref in deducted:
                db.products.update_one(
                    {"product_name": ref["product_name"]},
                    {"$inc": {"quantity": ref["quantity"]}}
                )
            if inserted_tx_ids:
                db.inventory_transactions.delete_many({"_id": {"$in": [ObjectId(t) for t in inserted_tx_ids if ObjectId.is_valid(t)]}})
            _log_rejected_attempt(performed_by, items, err, customer_data)
            return False, err, {}
        deducted.append({"product_name": item["product_name"], "quantity": item["quantity"]})
        if tx_id:
            inserted_tx_ids.append(tx_id)

    # ── Build bill document ──
    bill_doc = {
        "bill_number": bill_number,
        "customer_name": computed["customer_name"],
        "customer_phone": computed["customer_phone"],
        "customer_gstin": computed["customer_gstin"],
        "payment_method": computed["payment_method"],
        "payment_status": computed["payment_status"],
        "line_items": computed["line_items"],
        "subtotal": computed["subtotal"],
        "total_line_discount": computed["total_line_discount"],
        "discount_percent": computed["discount_percent"],
        "discount_amount": computed["discount_amount"],
        "cgst_total": computed["cgst_total"],
        "sgst_total": computed["sgst_total"],
        "gst_total": computed["gst_total"],
        "free_total": computed["free_total"],
        "shipping_charge": computed["shipping_charge"],
        "packing_charge": computed["packing_charge"],
        "charges_total": computed["charges_total"],
        "round_off": computed["round_off"],
        "grand_total": computed["grand_total"],
        "amount_paid": computed["amount_paid"],
        "amount_due": computed["amount_due"],
        "due_date": computed.get("due_date"),
        "refunded_at": None,
        "refunded_by": None,
        "refund_reason": None,
        "refund_history": [],
        "edit_history": [],
        "created_by": performed_by,
        "created_at": now,
    }

    # ── Insert bill + payments + audit ──
    try:
        res = db.invoices.insert_one(bill_doc)
        bill_doc["_id"] = str(res.inserted_id)

        # Write bill_payments records for each split
        for split in computed.get("payment_splits", []):
            db.bill_payments.insert_one({
                "bill_id": res.inserted_id,
                "bill_number": bill_number,
                "amount": float(split.get("amount", 0)),
                "method": (split.get("method") or computed["payment_method"]).upper(),
                "reference": (split.get("reference") or "").strip(),
                "performed_by": performed_by,
                "created_at": now,
            })

        # If non-split and paid, also record a single payment entry
        if not computed.get("payment_splits") and computed["amount_paid"] > 0:
            db.bill_payments.insert_one({
                "bill_id": res.inserted_id,
                "bill_number": bill_number,
                "amount": computed["amount_paid"],
                "method": computed["payment_method"],
                "reference": "",
                "performed_by": performed_by,
                "created_at": now,
            })

        # Immutable audit snapshot
        snapshot = _bill_snapshot(bill_doc)
        log_audit("BILL_CREATE", performed_by, bill_number, {
            "grand_total": computed["grand_total"],
            "items": len(computed["line_items"]),
            "customer": computed["customer_name"],
            "snapshot": snapshot,
        })

        return True, f"Bill {bill_number} created successfully.", bill_doc

    except Exception as e:
        for ref in deducted:
            db.products.update_one(
                {"product_name": ref["product_name"]},
                {"$inc": {"quantity": ref["quantity"]}}
            )
        if inserted_tx_ids:
            db.inventory_transactions.delete_many({"_id": {"$in": [ObjectId(t) for t in inserted_tx_ids if ObjectId.is_valid(t)]}})
        return False, f"Failed to create bill: {str(e)}", {}


# ──────────────────────────────────────────────────────────────────────
# Record payment against a bill
# ──────────────────────────────────────────────────────────────────────

def record_bill_payment(bill_id: str, amount: float, method: str,
                        reference: str, performed_by: str) -> tuple[bool, str]:
    """Records a payment (full or partial) against a bill."""
    db = get_db()
    bill = get_bill_by_id(bill_id)
    if not bill:
        return False, "Bill not found."

    if bill.get("payment_status") in ("PAID", "REFUNDED"):
        return False, f"Bill is already {bill['payment_status']}."

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return False, "Payment amount must be a valid number."

    if amount <= 0:
        return False, "Payment amount must be greater than zero."

    remaining = _round2(float(bill.get("grand_total", 0)) - float(bill.get("amount_paid", 0)))
    if amount > remaining:
        return False, f"Payment amount ({amount}) exceeds remaining balance ({remaining})."

    method = (method or 'CASH').strip().upper()
    if method not in ('CASH', 'UPI', 'CARD', 'CREDIT'):
        return False, "Payment method must be CASH, UPI, CARD or CREDIT."

    now = datetime.now(timezone.utc)

    new_amount_paid = _round2(float(bill.get("amount_paid", 0)) + amount)
    new_amount_due = _round2(max(0, float(bill.get("grand_total", 0)) - new_amount_paid))
    new_status = "PAID" if new_amount_due <= 0 else "PARTIAL"

    result = db.invoices.update_one(
        {"_id": ObjectId(bill_id), "payment_status": {"$nin": ["PAID", "REFUNDED"]}},
        {"$set": {
            "amount_paid": new_amount_paid,
            "amount_due": new_amount_due,
            "payment_status": new_status,
        }}
    )

    if result.matched_count == 0:
        return False, "Bill not found or already paid/refunded."

    db.bill_payments.insert_one({
        "bill_id": ObjectId(bill_id),
        "bill_number": bill.get("bill_number"),
        "amount": amount,
        "method": method,
        "reference": reference.strip() if reference else "",
        "performed_by": performed_by,
        "created_at": now,
    })

    log_audit("BILL_PAYMENT", performed_by, bill.get("bill_number"), {
        "amount": amount,
        "method": method,
        "reference": reference,
        "new_status": new_status,
        "amount_paid": new_amount_paid,
        "amount_due": new_amount_due,
    })

    return True, f"Payment of {amount} recorded successfully."


# ──────────────────────────────────────────────────────────────────────
# Refund specific line(s)
# ──────────────────────────────────────────────────────────────────────

def refund_bill_lines(bill_id: str, line_indices: list, reason: str, performed_by: str) -> tuple[bool, str]:
    """Refunds specific line(s) by index, restores stock, updates payment status."""
    db = get_db()
    bill = get_bill_by_id(bill_id)
    if not bill:
        return False, "Bill not found."

    if bill.get("payment_status") == "REFUNDED":
        return False, "Bill has already been fully refunded."

    now = datetime.now(timezone.utc)
    reason_clean = (reason or "Line refund").strip()
    line_items = bill.get("line_items", [])

    if not line_indices or not isinstance(line_indices, list):
        return False, "No line items selected for refund."

    # Validate indices
    refund_total = 0.0
    lines_to_refund = []
    for idx in line_indices:
        try:
            i = int(idx)
        except (ValueError, TypeError):
            continue
        if i < 0 or i >= len(line_items):
            return False, f"Invalid line index {i}."
        line = line_items[i]
        if line.get("is_refunded"):
            return False, f"Line {i} ({line.get('product_name', '?')}) is already refunded."
        refund_qty = float(line.get("quantity", 0)) - float(line.get("refund_quantity", 0))
        if refund_qty <= 0:
            return False, f"Nothing to refund for line {i} ({line.get('product_name', '?')})."
        lines_to_refund.append((i, line, refund_qty))
        refund_total = _round2(refund_total + float(line.get("line_total", 0)) * refund_qty / float(line.get("quantity", 1)))

    # Restore stock + mark lines
    for i, line, refund_qty in lines_to_refund:
        prod_name = line.get("product_name")
        full_qty = float(line.get("quantity", 1))
        fraction = refund_qty / full_qty

        # Restore stock
        _restore_stock(
            db, prod_name, refund_qty, now, performed_by,
            reason=f"Refund line {i} for bill {bill.get('bill_number')}: {reason_clean}"
        )

        # Update line in-memory and for DB update
        line["is_refunded"] = True
        line["refund_quantity"] = full_qty  # full line refund

    # Compute refund total from line totals
    refund_amount = _round2(sum(float(l.get("line_total", 0)) for _, l, _ in lines_to_refund))

    # Update bill
    new_refund_history = bill.get("refund_history", [])
    new_refund_history.append({
        "line_indices": line_indices,
        "reason": reason_clean,
        "amount": refund_amount,
        "performed_by": performed_by,
        "created_at": now,
    })

    total_refunded = _round2(sum(r["amount"] for r in new_refund_history))
    grand_total = float(bill.get("grand_total", 0))

    if total_refunded >= grand_total:
        new_status = "REFUNDED"
    elif float(bill.get("amount_paid", 0)) >= (grand_total - total_refunded):
        new_status = "PAID"
    elif float(bill.get("amount_paid", 0)) > 0:
        new_status = "PARTIAL"
    else:
        new_status = "DUE"

    db.invoices.update_one(
        {"_id": ObjectId(bill_id)},
        {"$set": {
            "line_items": line_items,
            "payment_status": new_status,
            "refund_history": new_refund_history,
        }}
    )

    log_audit("BILL_REFUND_LINE", performed_by, bill.get("bill_number"), {
        "line_indices": line_indices,
        "refund_amount": refund_amount,
        "reason": reason_clean,
        "new_status": new_status,
    })

    return True, f"Refund of {refund_amount} processed for {len(lines_to_refund)} line(s)."


# ──────────────────────────────────────────────────────────────────────
# Edit bill (admin/inventory_manager only)
# ──────────────────────────────────────────────────────────────────────

def edit_bill(bill_id: str, new_items: list, charges: dict,
              customer_data: dict, performed_by: str) -> tuple[bool, str, dict]:
    """
    Edits an existing bill's line items and charges.
    Computes stock delta (removed items restored, new items deducted).
    Records BILL_EDIT audit with before/after snapshot.
    """
    db = get_db()
    bill = get_bill_by_id(bill_id)
    if not bill:
        return False, "Bill not found.", {}

    if bill.get("payment_status") == "REFUNDED":
        return False, "Cannot edit a refunded bill.", {}

    # Merge customer_data from bill (preserve customer info unless updated)
    merged_customer = {
        "customer_name": customer_data.get("customer_name") or bill.get("customer_name", ""),
        "customer_phone": customer_data.get("customer_phone") or bill.get("customer_phone", ""),
        "customer_gstin": customer_data.get("customer_gstin") or bill.get("customer_gstin", ""),
        "payment_method": customer_data.get("payment_method") or bill.get("payment_method", "CASH"),
        "discount_percent": customer_data.get("discount_percent") if customer_data.get("discount_percent") is not None else bill.get("discount_percent", 0),
        "due_date": customer_data.get("due_date") or bill.get("due_date"),
    }

    # Compute new bill
    items_with_products = []
    for raw_item in new_items:
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

        items_with_products.append({
            "product_name": product["product_name"],
            "product": product,
            "quantity": quantity,
            "line_discount_percent": float(raw_item.get('line_discount_percent', 0) or 0),
            "is_free": bool(raw_item.get('is_free', False)),
        })

    ok, msg, computed = compute_bill(merged_customer, items_with_products, charges, bill.get("payment_splits"))
    if not ok:
        return False, msg, {}

    now = datetime.now(timezone.utc)
    old_items = bill.get("line_items", [])

    # ── Compute stock delta ──
    old_qty_map = {}
    for item in old_items:
        name = item["product_name"]
        qty = float(item.get("quantity", 0))
        refunded_qty = float(item.get("refund_quantity", 0))
        old_qty_map[name] = old_qty_map.get(name, 0) + (qty - refunded_qty)

    new_qty_map = {}
    for item in computed["line_items"]:
        name = item["product_name"]
        new_qty_map[name] = new_qty_map.get(name, 0) + float(item["quantity"])

    # Products to restore (removed or reduced)
    for name, old_qty in old_qty_map.items():
        new_qty = new_qty_map.get(name, 0)
        if old_qty > new_qty:
            restore_qty = old_qty - new_qty
            _restore_stock(db, name, restore_qty, now, performed_by,
                           reason=f"Bill edit: removed from {bill.get('bill_number')}")

    # Products to deduct (added or increased)
    deducted = []
    inserted_tx_ids = []
    for name, new_qty in new_qty_map.items():
        old_qty = old_qty_map.get(name, 0)
        if new_qty > old_qty:
            deduct_qty = new_qty - old_qty
            success, err, tx_id = _deduct_stock(db, name, deduct_qty, now, performed_by)
            if not success:
                # Rollback all deductions so far
                for ref in deducted:
                    db.products.update_one(
                        {"product_name": ref["product_name"]},
                        {"$inc": {"quantity": ref["quantity"]}}
                    )
                if inserted_tx_ids:
                    db.inventory_transactions.delete_many({"_id": {"$in": [ObjectId(t) for t in inserted_tx_ids if ObjectId.is_valid(t)]}})
                return False, f"Stock deduction failed for '{name}': {err}", {}
            deducted.append({"product_name": name, "quantity": deduct_qty})
            if tx_id:
                inserted_tx_ids.append(tx_id)

    # ── Update bill ──
    edit_snapshot = _bill_snapshot(bill)
    new_edit_history = bill.get("edit_history", [])
    new_edit_history.append({
        "snapshot": edit_snapshot,
        "performed_by": performed_by,
        "created_at": now,
        "reason": "Bill edited",
    })

    # Recompute amount_paid / amount_due based on existing payments
    existing_paid = float(bill.get("amount_paid", 0))
    new_grand = computed["grand_total"]
    new_due = _round2(max(0, new_grand - existing_paid))
    if existing_paid >= new_grand:
        new_status = "PAID"
        existing_paid = new_grand
        new_due = 0.0
    elif existing_paid > 0:
        new_status = "PARTIAL"
    else:
        new_status = "DUE"

    db.invoices.update_one(
        {"_id": ObjectId(bill_id)},
        {"$set": {
            "line_items": computed["line_items"],
            "subtotal": computed["subtotal"],
            "total_line_discount": computed["total_line_discount"],
            "discount_percent": computed["discount_percent"],
            "discount_amount": computed["discount_amount"],
            "cgst_total": computed["cgst_total"],
            "sgst_total": computed["sgst_total"],
            "gst_total": computed["gst_total"],
            "free_total": computed["free_total"],
            "shipping_charge": computed["shipping_charge"],
            "packing_charge": computed["packing_charge"],
            "charges_total": computed["charges_total"],
            "round_off": computed["round_off"],
            "grand_total": new_grand,
            "amount_paid": existing_paid,
            "amount_due": new_due,
            "payment_status": new_status,
            "edit_history": new_edit_history,
        }}
    )

    log_audit("BILL_EDIT", performed_by, bill.get("bill_number"), {
        "edit_index": len(new_edit_history),
        "old_item_count": len(old_items),
        "new_item_count": len(computed["line_items"]),
        "old_grand_total": bill.get("grand_total"),
        "new_grand_total": new_grand,
    })

    updated_bill = get_bill_by_id(bill_id)
    return True, f"Bill {bill.get('bill_number')} updated successfully.", updated_bill


# ──────────────────────────────────────────────────────────────────────
# Full bill refund (existing, updated)
# ──────────────────────────────────────────────────────────────────────

def refund_bill(bill_id: str, reason: str, performed_by: str) -> tuple[bool, str]:
    """Cancels/refunds an entire invoice, restores stock, records transaction/audit logs."""
    db = get_db()
    bill = get_bill_by_id(bill_id)
    if not bill:
        return False, "Bill not found."

    if bill.get("payment_status") == "REFUNDED":
        return False, "Bill has already been refunded."

    now = datetime.now(timezone.utc)
    reason_clean = (reason or "Customer refund").strip()

    for item in bill.get("line_items", []):
        prod_name = item.get("product_name")
        qty = float(item.get("quantity", 0))
        refunded_qty = float(item.get("refund_quantity", 0))
        net_qty = qty - refunded_qty
        if prod_name and net_qty > 0:
            _restore_stock(
                db, prod_name, net_qty, now, performed_by,
                reason=f"Refund for bill {bill.get('bill_number')}: {reason_clean}"
            )
            item["is_refunded"] = True
            item["refund_quantity"] = qty

    new_refund_history = bill.get("refund_history", [])
    new_refund_history.append({
        "line_indices": list(range(len(bill.get("line_items", [])))),
        "reason": reason_clean,
        "amount": bill.get("grand_total", 0),
        "performed_by": performed_by,
        "created_at": now,
    })

    db.invoices.update_one(
        {"_id": ObjectId(bill_id)},
        {"$set": {
            "payment_status": "REFUNDED",
            "amount_due": 0.0,
            "refunded_at": now,
            "refunded_by": performed_by,
            "refund_reason": reason_clean,
            "line_items": bill.get("line_items", []),
            "refund_history": new_refund_history,
        }}
    )
    log_audit("BILL_REFUND", performed_by, bill.get("bill_number"), {"reason": reason_clean})
    return True, f"Bill {bill.get('bill_number')} refunded successfully and inventory stock restored."


# ──────────────────────────────────────────────────────────────────────
# Queries
# ──────────────────────────────────────────────────────────────────────

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


def get_bills(search: str = "", limit: int = 100, payment_status: str = "") -> list:
    """Lists invoices, newest first, with optional bill number/customer search and status filter."""
    db = get_db()
    query = {}
    search = search.strip()
    if search:
        escaped = re.escape(search)
        query["$or"] = [
            {"bill_number": {"$regex": escaped, "$options": "i"}},
            {"customer_name": {"$regex": escaped, "$options": "i"}}
        ]
    if payment_status:
        query["payment_status"] = payment_status.strip().upper()
    projection = {
        "bill_number": 1,
        "customer_name": 1,
        "customer_phone": 1,
        "payment_method": 1,
        "payment_status": 1,
        "grand_total": 1,
        "amount_paid": 1,
        "amount_due": 1,
        "created_at": 1,
        "created_by": 1,
        "line_items": 1,
    }
    bills = list(db.invoices.find(query, projection).sort("created_at", -1).limit(limit))
    for b in bills:
        b["_id"] = str(b["_id"])
    return bills


def get_billing_summary() -> dict:
    """Returns billing metrics for the dashboard using aggregation (no full scan)."""
    db = get_db()
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Today's stats via aggregation
    today_pipeline = [
        {"$match": {"created_at": {"$gte": start_of_today}}},
        {"$group": {
            "_id": None,
            "today_bills": {"$sum": 1},
            "today_sales": {"$sum": "$grand_total"},
        }}
    ]
    today_result = list(db.invoices.aggregate(today_pipeline))
    today_bills = today_result[0]["today_bills"] if today_result else 0
    today_sales = today_result[0]["today_sales"] if today_result else 0.0

    total_bills = db.invoices.count_documents({})

    # All-time totals via aggregation
    all_pipeline = [
        {"$group": {
            "_id": None,
            "total_sales": {"$sum": "$grand_total"},
            "total_outstanding": {
                "$sum": {
                    "$cond": [
                        {"$in": ["$payment_status", ["DUE", "PARTIAL"]]},
                        "$amount_due",
                        0
                    ]
                }
            },
        }}
    ]
    all_result = list(db.invoices.aggregate(all_pipeline))
    total_sales = all_result[0]["total_sales"] if all_result else 0.0
    total_outstanding = all_result[0]["total_outstanding"] if all_result else 0.0

    return {
        "total_bills": total_bills,
        "today_bills": today_bills,
        "today_sales": float(today_sales),
        "total_sales": float(total_sales),
        "total_outstanding": float(total_outstanding),
    }


def get_bill_payments(bill_id: str) -> list:
    """Returns payment records for a bill."""
    db = get_db()
    try:
        payments = list(db.bill_payments.find({"bill_id": ObjectId(bill_id)}).sort("created_at", 1))
    except Exception:
        payments = list(db.bill_payments.find({"bill_number": bill_id}).sort("created_at", 1))
    for p in payments:
        p["_id"] = str(p["_id"])
        if "bill_id" in p and isinstance(p["bill_id"], ObjectId):
            p["bill_id"] = str(p["bill_id"])
    return payments


def get_bill_audit_history(bill_number: str) -> list:
    """Returns audit log entries for a specific bill."""
    db = get_db()
    logs = list(db.audit_logs.find(
        {"target_resource": bill_number}
    ).sort("created_at", -1).limit(50))
    for log in logs:
        log["_id"] = str(log["_id"])
    return logs


# ──────────────────────────────────────────────────────────────────────
# Reconciliation report
# ──────────────────────────────────────────────────────────────────────

def get_reconciliation_report() -> list:
    """
    Cross-checks invoices vs inventory_transactions vs audit_logs
    and returns a list of anomalies.
    """
    db = get_db()
    anomalies = []

    all_bills = list(db.invoices.find({}, {"line_items": 1, "bill_number": 1, "created_by": 1,
                                            "created_at": 1, "grand_total": 1, "subtotal": 1,
                                            "gst_total": 1, "payment_status": 1, "amount_paid": 1,
                                            "amount_due": 1, "discount_amount": 1,
                                            "shipping_charge": 0, "packing_charge": 0,
                                            "round_off": 0})).limit(5000)

    for bill in all_bills:
        bill_id = bill["_id"]
        bill_number = bill.get("bill_number", "")
        items = bill.get("line_items", [])

        # ── Arithmetic check per line ──
        for i, line in enumerate(items):
            qty = float(line.get("quantity", 0))
            price = float(line.get("unit_price", 0))
            disc = float(line.get("line_discount_amount", 0))
            taxable = float(line.get("taxable", 0))
            expected_taxable = round(qty * price - disc, 2)
            if abs(taxable - expected_taxable) > 0.02:
                anomalies.append({
                    "type": "ARITHMETIC_MISMATCH",
                    "bill_number": bill_number,
                    "line_index": i,
                    "product": line.get("product_name"),
                    "detail": f"Taxable {taxable} != expected {expected_taxable}",
                    "cashier": bill.get("created_by"),
                    "created_at": bill.get("created_at"),
                })

            # ── Zero/negative quantity stored ──
            if qty <= 0:
                anomalies.append({
                    "type": "NON_POSITIVE_QTY",
                    "bill_number": bill_number,
                    "line_index": i,
                    "product": line.get("product_name"),
                    "detail": f"Stored quantity = {qty}",
                    "cashier": bill.get("created_by"),
                    "created_at": bill.get("created_at"),
                })

            # ── Free line flagged ──
            if line.get("is_free") and qty > 0 and float(line.get("line_total", 0)) > 0:
                anomalies.append({
                    "type": "FREE_LINE_WITH_VALUE",
                    "bill_number": bill_number,
                    "line_index": i,
                    "product": line.get("product_name"),
                    "detail": f"is_free=True but line_total={line.get('line_total')}",
                    "cashier": bill.get("created_by"),
                    "created_at": bill.get("created_at"),
                })

        # ── Check BILL_SALE transactions exist for each line ──
        for i, line in enumerate(items):
            qty = float(line.get("quantity", 0))
            refunded_qty = float(line.get("refund_quantity", 0))
            net_qty = qty - refunded_qty
            if net_qty <= 0:
                continue
            tx = db.inventory_transactions.find_one({
                "product_name": line.get("product_name"),
                "transaction_type": "BILL_SALE",
                "reason": {"$regex": re.escape(bill_number)},
            })
            if not tx:
                anomalies.append({
                    "type": "MISSING_SALE_TX",
                    "bill_number": bill_number,
                    "line_index": i,
                    "product": line.get("product_name"),
                    "detail": f"No BILL_SALE transaction for {net_qty} units",
                    "cashier": bill.get("created_by"),
                    "created_at": bill.get("created_at"),
                })

        # ── DUE/PARTIAL bills without payments ──
        if bill.get("payment_status") in ("DUE", "PARTIAL"):
            payments = list(db.bill_payments.find({"bill_number": bill_number}))
            total_payments = sum(float(p.get("amount", 0)) for p in payments)
            if total_payments < float(bill.get("amount_paid", 0)) - 0.02:
                anomalies.append({
                    "type": "PAYMENT_MISMATCH",
                    "bill_number": bill_number,
                    "detail": f"amount_paid={bill.get('amount_paid')} but bill_payments sum={total_payments}",
                    "cashier": bill.get("created_by"),
                    "created_at": bill.get("created_at"),
                })

    return anomalies
