import re
import time
import json
import logging
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from inventory_app.database import get_db

logger = logging.getLogger(__name__)
from inventory_app.utils.validators import normalize_product_name, validate_product_data
from inventory_app.utils.helpers import calculate_stock_status
from inventory_app.services.audit_service import log_audit
from inventory_app import cache_get, cache_set, cache_delete, cache_delete_prefix

# ── Product lookup cache TTL (global via Upstash on Vercel) ──
_PRODUCT_CACHE_TTL = 30

def create_product(product_data: dict, performed_by: str, initial_quantity: float = None) -> tuple[bool, str, dict]:
    """
    Creates a new product in MongoDB.
    Validates input, checks name uniqueness, calculates initial stock status,
    and inserts INITIAL_STOCK transaction if initial quantity > 0.
    initial_quantity overrides the default quantity (5) when provided.
    """
    db = get_db()
    
    # 1. Validate data structure
    is_valid, err_msg = validate_product_data(product_data)
    if not is_valid:
        return False, err_msg, {}
        
    raw_name = product_data.get('product_name', '')
    product_name = normalize_product_name(raw_name)
    
    # 2. Check case-insensitive duplicate product_name
    existing = db.products.find_one({"product_name_lower": product_name.lower()})
    if existing:
        return False, f"A product with the name '{product_name}' already exists.", {}
        
    quantity = initial_quantity if initial_quantity is not None else 5
    minimum_stock = 5
    price = float(product_data.get('price', 0))
    gst_rate = float(product_data.get('gst_rate', 0))
    hsn_code = (product_data.get('hsn_code') or '').strip().upper()
    
    now = datetime.now(timezone.utc)
    product_doc = {
        "product_name": product_name,
        "product_name_lower": product_name.lower(),
        "category": (product_data.get('category') or '').strip(),
        "description": (product_data.get('description') or '').strip(),
        "quantity": quantity,
        "unit": (product_data.get('unit') or '').strip(),
        "price": price,
        "gst_rate": gst_rate,
        "hsn_code": hsn_code,
        "minimum_stock": minimum_stock,
        "location": (product_data.get('location') or '').strip(),
        "is_active": True,
        "created_at": now,
        "updated_at": now
    }
    
    try:
        res = db.products.insert_one(product_doc)
        product_doc["_id"] = str(res.inserted_id)
        product_doc["status"] = calculate_stock_status(quantity, minimum_stock)
        
        # Record INITIAL_STOCK transaction if initial quantity > 0
        if quantity > 0:
            db.inventory_transactions.insert_one({
                "product_name": product_name,
                "transaction_type": "INITIAL_STOCK",
                "quantity": quantity,
                "previous_quantity": 0,
                "new_quantity": quantity,
                "reason": "Initial product registration",
                "performed_by": performed_by,
                "created_at": now
            })
            
        log_audit("PRODUCT_CREATE", performed_by, product_name, {"initial_stock": quantity})
        invalidate_product_cache(product_name)
        return True, f"Product '{product_name}' created successfully.", product_doc
    except DuplicateKeyError as e:
        err_str = str(e)
        if "product_name" in err_str:
            return False, f"A product with the name '{product_name}' already exists.", {}
        else:
            logger.error(f"Duplicate key error on index: {err_str}")
            return False, f"Cannot create product due to a duplicate constraint on another field.", {}
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return False, "An unexpected error occurred while creating the product.", {}

def get_product_by_name(product_name: str) -> dict:
    """Retrieves product by normalized product_name (cached globally for10s)."""
    db = get_db()
    norm_name = normalize_product_name(product_name)
    
    # Check global cache (Upstash on Vercel, redislite locally)
    cache_key = f"product:{norm_name}"
    cached = cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    
    product = db.products.find_one({"product_name": norm_name})
    if not product:
        # Case-insensitive fallback lookup via indexed lowercase field
        product = db.products.find_one({"product_name_lower": norm_name.lower()})
        
    if product:
        product["_id"] = str(product["_id"])
        product["status"] = calculate_stock_status(
            product.get("quantity", 0)
        )
    
    # Cache result globally
    if product:
        cache_set(cache_key, json.dumps(product, default=str), ttl=_PRODUCT_CACHE_TTL)
    
    return product


def invalidate_product_cache(product_name: str = None):
    """Invalidates product cache globally. Call after stock changes."""
    if product_name:
        cache_delete(f"product:{normalize_product_name(product_name)}")
    # Search results, category/location facets, dashboard and low-stock alerts
    # all derive from product state — drop them so writes are visible immediately.
    cache_delete_prefix("products:search:")
    cache_delete("products:categories")
    cache_delete("products:locations")
    cache_delete("dashboard:main")
    cache_delete_prefix("alerts:low_stock")

def search_products(query: str = "", category: str = "", location: str = "", stock_status: str = "", is_active: bool = True, sort_by: str = "product_name", sort_dir: int = 1, limit: int = 50, page: int = None, per_page: int = 25, return_total: bool = False):
    """
    Searches and filters products using server-side MongoDB query.
    Supports server-side pagination (page & per_page) with total count projection.
    Results are cached for 15 seconds to avoid redundant DB hits across routes.
    """
    import hashlib
    effective_page = page if page is not None else 1
    effective_limit = per_page if page is not None else limit
    effective_skip = (effective_page - 1) * effective_limit if page is not None else 0

    # Build a stable cache key from all filter parameters
    _key_parts = f"{query}|{category}|{location}|{stock_status}|{is_active}|{sort_by}|{sort_dir}|{effective_limit}|{effective_skip}|{return_total}"
    _cache_key = "products:search:" + hashlib.md5(_key_parts.encode()).hexdigest()

    cached = cache_get(_cache_key)
    if cached is not None:
        try:
            cached_data = json.loads(cached)
            if return_total:
                return cached_data.get("items", []), cached_data.get("total", 0)
            return cached_data if isinstance(cached_data, list) else cached_data.get("items", [])
        except (TypeError, ValueError):
            pass

    db = get_db()
    filter_query = {}
    
    if is_active is not None:
        filter_query["is_active"] = is_active
        
    if query:
        norm_query = normalize_product_name(query)
        # Indexed case-insensitive substring search via product_name_lower
        filter_query["product_name_lower"] = {"$regex": re.escape(norm_query.lower()), "$options": "i"}
        
    if category:
        filter_query["category"] = category
        
    if location:
        filter_query["location"] = location

    # Push stock_status filter to MongoDB — avoids fetching then discarding in Python
    if stock_status:
        min_stock_expr = {"$ifNull": ["$minimum_stock", 5]}
        if stock_status == "OUT OF STOCK":
            filter_query["$expr"] = {"$lte": ["$quantity", 0]}
        elif stock_status == "LOW STOCK":
            filter_query["$expr"] = {
                "$and": [
                    {"$gt": ["$quantity", 0]},
                    {"$lte": ["$quantity", min_stock_expr]}
                ]
            }
        elif stock_status == "IN STOCK":
            filter_query["$expr"] = {"$gt": ["$quantity", min_stock_expr]}
        
    projection = {
        "product_name": 1,
        "category": 1,
        "quantity": 1,
        "minimum_stock": 1,
        "price": 1,
        "gst_rate": 1,
        "unit": 1,
        "hsn_code": 1,
        "location": 1,
        "is_active": 1,
    }

    # Single-query pagination: fetch limit+1 rows to detect "has more" without a
    # separate count_documents call (avoids scanning the same query twice).
    fetch_limit = effective_limit + 1 if (return_total and effective_limit) else effective_limit

    cursor = db.products.find(filter_query, projection).sort(sort_by, sort_dir)
    if effective_skip > 0:
        cursor = cursor.skip(effective_skip)
    if fetch_limit is not None and fetch_limit > 0:
        cursor = cursor.limit(fetch_limit)

    products = list(cursor)
    has_more = len(products) > effective_limit if effective_limit else False
    if has_more:
        products = products[:effective_limit]
    
    result = []
    for p in products:
        p["_id"] = str(p["_id"])
        p["status"] = calculate_stock_status(p.get("quantity", 0))
        result.append(p)

    if return_total:
        # When has_more is False we fetched ≤ effective_limit from a limit+1 query,
        # so we are on the last page and the true total is skip + items returned.
        total_count = (effective_skip + len(result)) if not has_more else db.products.count_documents(filter_query)
        cache_set(_cache_key, json.dumps({"items": result, "total": total_count}, default=str), ttl=15)
        return result, total_count
    else:
        cache_set(_cache_key, json.dumps(result, default=str), ttl=15)
        return result

def update_product(product_name: str, update_data: dict, performed_by: str) -> tuple[bool, str, dict]:
    """Updates product attributes (excluding product_name)."""
    db = get_db()
    product = get_product_by_name(product_name)
    if not product:
        return False, "Product not found.", {}
        
    norm_name = product["product_name"]
    
    # Validate non-name data
    try:
        price = float(update_data.get('price', product.get('price', 0)))
        if price < 0:
            return False, "Price cannot be negative.", {}
    except (ValueError, TypeError):
        return False, "Price must be a valid number.", {}

    try:
        gst_rate = float(update_data.get('gst_rate', product.get('gst_rate', 0)))
        if gst_rate < 0 or gst_rate > 28:
            return False, "GST rate must be between 0% and 28%.", {}
    except (ValueError, TypeError):
        return False, "GST rate must be a valid number.", {}

    hsn_code = (update_data.get('hsn_code') or product.get('hsn_code') or '').strip().upper()
    if len(hsn_code) > 8:
        return False, "HSN code cannot exceed 8 characters.", {}

    category = (update_data.get('category') or product.get('category')).strip()
    if not category:
        return False, "Category is required.", {}
        
    unit = (update_data.get('unit') or product.get('unit')).strip()
    if not unit:
        return False, "Unit of measure is required.", {}

    now = datetime.now(timezone.utc)
    set_fields = {
        "category": category,
        "description": (update_data.get('description') or '').strip(),
        "unit": unit,
        "price": price,
        "gst_rate": gst_rate,
        "hsn_code": hsn_code,
        "minimum_stock": 5,
        "location": (update_data.get('location') or '').strip(),
        "updated_at": now
    }
    
    try:
        db.products.update_one({"product_name": norm_name}, {"$set": set_fields})
        log_audit("PRODUCT_UPDATE", performed_by, norm_name, set_fields)
        invalidate_product_cache(norm_name)
        updated_prod = get_product_by_name(norm_name)
        return True, f"Product '{norm_name}' updated successfully.", updated_prod
    except Exception as e:
        logger.error(f"Failed to update product: {e}")
        return False, "An unexpected error occurred while updating the product.", {}

def rename_product(old_name: str, new_name: str, performed_by: str) -> tuple[bool, str]:
    """
    Renames a product (Admin operation).
    Validates new_name, verifies uniqueness, updates product document,
    updates transaction history, creates a PRODUCT_RENAME transaction, and logs audit.
    """
    db = get_db()
    product = get_product_by_name(old_name)
    if not product:
        return False, "Original product not found."
        
    canonical_old_name = product["product_name"]
    canonical_new_name = normalize_product_name(new_name)
    
    if not canonical_new_name:
        return False, "New product name is required."
        
    if canonical_old_name == canonical_new_name:
        return False, "New product name is identical to the current name."
        
    # Check if target new_name already exists
    existing = db.products.find_one({"product_name_lower": canonical_new_name.lower()})
    if existing:
        return False, f"Product name '{canonical_new_name}' is already in use by another product."
        
    now = datetime.now(timezone.utc)
    try:
        # Update product document
        res = db.products.update_one(
            {"product_name": canonical_old_name},
            {"$set": {"product_name": canonical_new_name, "product_name_lower": canonical_new_name.lower(), "updated_at": now}}
        )
        
        if res.matched_count == 0:
            return False, "Failed to update product name."
            
        # Update corresponding inventory transaction records
        db.inventory_transactions.update_many(
            {"product_name": canonical_old_name},
            {"$set": {"product_name": canonical_new_name}}
        )
        
        # Record PRODUCT_RENAME transaction
        db.inventory_transactions.insert_one({
            "product_name": canonical_new_name,
            "transaction_type": "PRODUCT_RENAME",
            "quantity": 0,
            "previous_quantity": product.get("quantity", 0),
            "new_quantity": product.get("quantity", 0),
            "reason": f"Renamed from '{canonical_old_name}' to '{canonical_new_name}'",
            "performed_by": performed_by,
            "created_at": now,
            "metadata": {"old_name": canonical_old_name, "new_name": canonical_new_name}
        })
        
        log_audit("PRODUCT_RENAME", performed_by, canonical_new_name, {
            "old_name": canonical_old_name,
            "new_name": canonical_new_name
        })
        invalidate_product_cache(canonical_old_name)
        invalidate_product_cache(canonical_new_name)
        
        return True, f"Product renamed from '{canonical_old_name}' to '{canonical_new_name}' successfully."
    except DuplicateKeyError:
        return False, f"Product name '{canonical_new_name}' already exists."
    except Exception as e:
        logger.error(f"Error renaming product: {e}")
        return False, "An unexpected error occurred while renaming the product."

def toggle_product_active(product_name: str, performed_by: str) -> tuple[bool, str, bool]:
    """Toggles product is_active state without destroying historical transaction data."""
    db = get_db()
    product = get_product_by_name(product_name)
    if not product:
        return False, "Product not found.", False
        
    norm_name = product["product_name"]
    new_status = not product.get("is_active", True)
    now = datetime.now(timezone.utc)
    
    db.products.update_one(
        {"product_name": norm_name},
        {"$set": {"is_active": new_status, "updated_at": now}}
    )
    
    action_str = "activated" if new_status else "deactivated"
    log_audit("PRODUCT_TOGGLE_ACTIVE", performed_by, norm_name, {"is_active": new_status})
    invalidate_product_cache(norm_name)
    return True, f"Product '{norm_name}' has been {action_str}.", new_status

def get_distinct_categories() -> list:
    """Returns distinct product categories (globally cached, 30s TTL)."""
    cached = cache_get("products:categories")
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    db = get_db()
    result = sorted([c for c in db.products.distinct("category") if c])
    cache_set("products:categories", json.dumps(result), ttl=_PRODUCT_CACHE_TTL)
    return result

def get_distinct_locations() -> list:
    """Returns distinct product locations (globally cached, 30s TTL)."""
    cached = cache_get("products:locations")
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    db = get_db()
    result = sorted([l for l in db.products.distinct("location") if l])
    cache_set("products:locations", json.dumps(result), ttl=_PRODUCT_CACHE_TTL)
    return result

def get_stock_by_category() -> list:
    """Aggregates active product stock quantity by category."""
    db = get_db()
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$category", "total_stock": {"$sum": "$quantity"}}},
        {"$sort": {"total_stock": -1}}
    ]
    results = list(db.products.aggregate(pipeline))
    return [{"category": r["_id"] or "Uncategorized", "total_stock": r["total_stock"]} for r in results]

def get_low_stock_by_category() -> list:
    """Aggregates count of low stock / out of stock active products by category (server-side)."""
    db = get_db()
    # LOW STOCK: quantity > 0 AND quantity < 5
    # OUT OF STOCK: quantity <= 0
    pipeline = [
        {"$match": {"is_active": True}},
        {"$addFields": {
            "is_low": {
                "$and": [
                    {"$gt": ["$quantity", 0]},
                    {"$lte": ["$quantity", 5]}
                ]
            },
            "is_out": {"$lte": ["$quantity", 0]}
        }},
        {"$match": {"$or": [{"is_low": True}, {"is_out": True}]}},
        {"$group": {"_id": "$category", "low_stock_count": {"$sum": 1}}},
        {"$sort": {"low_stock_count": -1}}
    ]
    results = list(db.products.aggregate(pipeline))
    return [{"category": r["_id"] or "Uncategorized", "low_stock_count": r["low_stock_count"]} for r in results]

def get_top_products_stock(limit: int = 10) -> list:
    """Retrieves top products by quantity for rendering in the bar chart."""
    db = get_db()
    products = list(db.products.find({"is_active": True}, {"product_name": 1, "quantity": 1}).sort("quantity", -1).limit(limit))
    return [{"product_name": p["product_name"], "quantity": p["quantity"]} for p in products]

def get_stock_alerts(limit: int = 6) -> list:
    """Retrieves active products at or below their minimum stock (LOW/OUT),
    worst first, for the navbar notification bell. Lightweight projection."""
    db = get_db()
    products = list(db.products.find(
        {"is_active": True, "$expr": {"$lte": ["$quantity", {"$ifNull": ["$minimum_stock", 5]}]}},
        {"product_name": 1, "quantity": 1, "unit": 1, "minimum_stock": 1}
    ).sort("quantity", 1).limit(limit))
    alerts = []
    for p in products:
        min_stock = p.get("minimum_stock", 5) or 5
        alerts.append({
            "product_name": p["product_name"],
            "quantity": float(p.get("quantity", 0) or 0),
            "unit": p.get("unit", ""),
            "minimum_stock": min_stock,
            "status": calculate_stock_status(p.get("quantity", 0), min_stock)
        })
    return alerts
