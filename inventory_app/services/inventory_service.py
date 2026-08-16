from datetime import datetime, timezone
from inventory_app.database import get_db
from inventory_app.services.product_service import get_product_by_name, invalidate_product_cache
from inventory_app.services.audit_service import log_audit
from inventory_app.utils.helpers import calculate_stock_status

def stock_in(product_name: str, quantity: float, reason: str, performed_by: str) -> tuple[bool, str, dict]:
    """
    Performs STOCK_IN operation.
    Validates quantity > 0, atomically increments stock, records transaction.
    """
    db = get_db()
    
    if quantity <= 0:
        return False, "Stock-in quantity must be greater than zero.", {}
        
    product = get_product_by_name(product_name)
    if not product:
        return False, f"Product '{product_name}' not found.", {}
        
    if not product.get("is_active", True):
        return False, f"Product '{product_name}' is inactive. Cannot perform stock operations.", {}
        
    canonical_name = product["product_name"]
    prev_qty = float(product.get("quantity", 0))
    new_qty = prev_qty + quantity
    now = datetime.now(timezone.utc)
    
    try:
        res = db.products.update_one(
            {"product_name": canonical_name},
            {
                "$inc": {"quantity": quantity},
                "$set": {"updated_at": now}
            }
        )
        
        if res.matched_count == 0:
            return False, "Product could not be updated.", {}
            
        # Record transaction
        tx_doc = {
            "product_name": canonical_name,
            "transaction_type": "STOCK_IN",
            "quantity": quantity,
            "previous_quantity": prev_qty,
            "new_quantity": new_qty,
            "reason": (reason or "Inventory received").strip(),
            "performed_by": performed_by,
            "created_at": now
        }
        db.inventory_transactions.insert_one(tx_doc)
        
        log_audit("STOCK_IN", performed_by, canonical_name, {"qty_added": quantity, "new_qty": new_qty})
        invalidate_product_cache(canonical_name)
        
        updated_product = get_product_by_name(canonical_name)
        return True, f"Successfully added {quantity} units to '{canonical_name}'.", updated_product
    except Exception as e:
        return False, "An unexpected error occurred during stock-in.", {}

def stock_out(product_name: str, quantity: float, reason: str, performed_by: str) -> tuple[bool, str, dict]:
    """
    Performs STOCK_OUT operation.
    Enforces non-negative inventory via atomic conditional query {$gte: quantity}.
    """
    db = get_db()
    
    if quantity <= 0:
        return False, "Stock-out quantity must be greater than zero.", {}
        
    product = get_product_by_name(product_name)
    if not product:
        return False, f"Product '{product_name}' not found.", {}
        
    if not product.get("is_active", True):
        return False, f"Product '{product_name}' is inactive. Cannot perform stock operations.", {}
        
    canonical_name = product["product_name"]
    prev_qty = float(product.get("quantity", 0))
    
    if prev_qty < quantity:
        return False, f"Insufficient stock for '{canonical_name}'. Available: {prev_qty}, Requested: {quantity}.", {}
        
    now = datetime.now(timezone.utc)
    
    try:
        # Atomic condition query prevents race condition stock-out below 0
        res = db.products.update_one(
            {
                "product_name": canonical_name,
                "quantity": {"$gte": quantity}
            },
            {
                "$inc": {"quantity": -quantity},
                "$set": {"updated_at": now}
            }
        )
        
        if res.modified_count == 0:
            # Re-fetch stock to give clear message if another thread changed it
            refreshed = get_product_by_name(canonical_name)
            curr_stock = refreshed.get("quantity", 0) if refreshed else 0
            return False, f"Stock-out failed. Insufficient available inventory (Current stock: {curr_stock}).", {}
            
        new_qty = prev_qty - quantity
        
        # Record transaction
        tx_doc = {
            "product_name": canonical_name,
            "transaction_type": "STOCK_OUT",
            "quantity": quantity,
            "previous_quantity": prev_qty,
            "new_quantity": new_qty,
            "reason": (reason or "Stock removed").strip(),
            "performed_by": performed_by,
            "created_at": now
        }
        db.inventory_transactions.insert_one(tx_doc)
        
        log_audit("STOCK_OUT", performed_by, canonical_name, {"qty_removed": quantity, "new_qty": new_qty})
        invalidate_product_cache(canonical_name)
        
        updated_product = get_product_by_name(canonical_name)
        return True, f"Successfully removed {quantity} units from '{canonical_name}'.", updated_product
    except Exception as e:
        return False, "An unexpected error occurred during stock-out.", {}

def stock_adjust(product_name: str, target_quantity: float, reason: str, performed_by: str) -> tuple[bool, str, dict]:
    """
    Performs manual ADJUSTMENT of product quantity.
    Requires mandatory reason and target_quantity >= 0.
    """
    db = get_db()
    
    if not reason or not reason.strip():
        return False, "A mandatory reason must be provided for stock adjustments.", {}
        
    if target_quantity < 0:
        return False, "Target stock quantity cannot be negative.", {}
        
    product = get_product_by_name(product_name)
    if not product:
        return False, f"Product '{product_name}' not found.", {}
        
    canonical_name = product["product_name"]
    prev_qty = float(product.get("quantity", 0))
    now = datetime.now(timezone.utc)
    
    diff = target_quantity - prev_qty
    
    try:
        res = db.products.update_one(
            {"product_name": canonical_name},
            {
                "$set": {
                    "quantity": target_quantity,
                    "updated_at": now
                }
            }
        )
        
        if res.matched_count == 0:
            return False, "Product could not be updated.", {}
            
        # Record ADJUSTMENT transaction
        tx_doc = {
            "product_name": canonical_name,
            "transaction_type": "ADJUSTMENT",
            "quantity": diff,
            "previous_quantity": prev_qty,
            "new_quantity": target_quantity,
            "reason": reason.strip(),
            "performed_by": performed_by,
            "created_at": now
        }
        db.inventory_transactions.insert_one(tx_doc)
        
        log_audit("ADJUSTMENT", performed_by, canonical_name, {
            "previous_qty": prev_qty,
            "target_qty": target_quantity,
            "diff": diff,
            "reason": reason
        })
        invalidate_product_cache(canonical_name)
        
        updated_product = get_product_by_name(canonical_name)
        return True, f"Stock for '{canonical_name}' adjusted to {target_quantity}.", updated_product
    except Exception as e:
        return False, "An unexpected error occurred while adjusting stock.", {}

def get_product_transactions(product_name: str, limit: int = 50) -> list:
    """Retrieves transaction history for a specific product."""
    db = get_db()
    norm_name = product_name.strip()
    txs = list(db.inventory_transactions.find({"product_name": norm_name}).sort("created_at", -1).limit(limit))
    for t in txs:
        t["_id"] = str(t["_id"])
    return txs

def get_all_transactions(product_name: str = "", transaction_type: str = "", limit: int = 100) -> list:
    """Retrieves inventory transactions with optional filtering."""
    db = get_db()
    query = {}
    
    if product_name:
        import re
        query["product_name"] = {"$regex": re.escape(product_name.strip()), "$options": "i"}
    if transaction_type:
        query["transaction_type"] = transaction_type
        
    txs = list(db.inventory_transactions.find(query).sort("created_at", -1).limit(limit))
    for t in txs:
        t["_id"] = str(t["_id"])
    return txs

def get_dashboard_metrics() -> dict:
    """
    Computes dashboard metrics via MongoDB aggregation (server-side).
    Avoids fetching all product documents into Python.
    """
    db = get_db()

    # Single aggregation pipeline computes all scalar metrics at once
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {
            "_id": None,
            "total_products": {"$sum": 1},
            "total_quantity": {"$sum": {"$toDouble": {"$ifNull": ["$quantity", 0]}}},
            "total_inventory_value": {"$sum": {
                "$multiply": [
                    {"$toDouble": {"$ifNull": ["$quantity", 0]}},
                    {"$toDouble": {"$ifNull": ["$price", 0]}}
                ]
            }},
            "out_of_stock_count": {"$sum": {"$cond": [
                {"$lte": [{"$toDouble": {"$ifNull": ["$quantity", 0]}}, 0]}, 1, 0
            ]}},
            "low_stock_count": {"$sum": {"$cond": [
                {"$and": [
                    {"$gt": [{"$toDouble": {"$ifNull": ["$quantity", 0]}}, 0]},
                    {"$lte": [
                        {"$toDouble": {"$ifNull": ["$quantity", 0]}},
                        {"$toDouble": {"$ifNull": ["$minimum_stock", 5]}}
                    ]}
                ]}, 1, 0
            ]}}
        }}
    ]

    agg = list(db.products.aggregate(pipeline))
    if agg:
        m = agg[0]
        total_products = m["total_products"]
        total_quantity = m["total_quantity"]
        total_inventory_value = m["total_inventory_value"]
        low_stock_count = m["low_stock_count"]
        out_of_stock_count = m["out_of_stock_count"]
    else:
        total_products = total_quantity = total_inventory_value = 0
        low_stock_count = out_of_stock_count = 0

    recent_transactions = list(db.inventory_transactions.find(
        {}, {"_id": 1, "product_name": 1, "transaction_type": 1,
             "quantity": 1, "created_at": 1, "performed_by": 1}
    ).sort("created_at", -1).limit(10))
    for t in recent_transactions:
        t["_id"] = str(t["_id"])

    return {
        "total_products": total_products,
        "total_quantity": total_quantity,
        "total_inventory_value": total_inventory_value,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "recent_transactions": recent_transactions
    }
