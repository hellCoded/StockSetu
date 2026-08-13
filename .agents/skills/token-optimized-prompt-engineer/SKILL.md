---
name: token-optimized-prompt-engineer
description: >-
  Reviews the StockSetu codebase and database schema to craft hyper-compact,
  token-optimized execution prompts. Uses concise technical shorthands, field projections,
  and minimal context footprint to achieve maximum development speed with minimal token consumption.
---

# Token-Optimized Prompt Engineer Skill

This skill instructs the agent on how to audit the StockSetu codebase and generate ultra-compact, token-efficient execution prompts whenever requested by the user.

---

## 🏛️ StockSetu Codebase & Database Quick Reference

### MongoDB Collections (`stocksetu_db`)
- `users`: `{_id, username, email, password_hash, role: 'admin'|'inventory_manager'|'staff', is_active}`
- `products`: `{_id, product_name, category, description, quantity, unit, price, gst_rate, hsn_code, minimum_stock, location, is_active, created_at, updated_at}`
- `invoices`: `{_id, bill_number, customer_name, customer_phone, payment_method, payment_status: 'PAID'|'REFUNDED', line_items: [{product_name, quantity, price, gst_rate}], subtotal, discount_percent, discount_amount, cgst_total, sgst_total, gst_total, grand_total, created_at}`
- `inventory_transactions`: `{_id, product_name, transaction_type: 'INITIAL_STOCK'|'STOCK_IN'|'STOCK_OUT'|'ADJUSTMENT'|'PRODUCT_RENAME'|'BILL_REFUND', quantity, previous_quantity, new_quantity, reason, performed_by, created_at}`
- `notifications`: `{_id, type: 'LOW_STOCK'|'OUT_OF_STOCK', product_name, current_stock, minimum_stock, is_read, created_at}`

### App Architecture
- **Flask App & Context Processor**: `inventory_app/__init__.py` (30s TTL cache for global badge counts).
- **Service Layer**: `inventory_app/services/` (`product_service.py`, `billing_service.py`, `inventory_service.py`, `notification_service.py`, `auth_service.py`, `audit_service.py`).
- **Blueprints/Routes**: `inventory_app/routes/` (`auth_routes.py`, `dashboard_routes.py`, `product_routes.py`, `inventory_routes.py`, `billing_routes.py`, `notification_routes.py`, `user_routes.py`).
- **Templates**: `inventory_app/templates/` (`base.html`, `components/sidebar.html`, `billing/pos.html`, `products/list.html`, etc.).

---

## ⚡ Token & Context Reduction Rules

When generating execution prompts or refactoring code:

1. **Zero Full-File Pastes**: Reference specific file paths and line ranges (e.g. `inventory_app/services/product_service.py#L105-L135`) rather than outputting entire source files.
2. **Explicit Field Projections**: Always mandate PyMongo projection dictionaries `{"field": 1}` for all `find()` queries to prevent BSON data bloat over the wire.
3. **Hard Query Limits**: Enforce `.limit(50)` on all list and summary queries.
4. **Session-First State Reads**: Read user session variables (`session.get('role')`, `session.get('username')`) to avoid hitting MongoDB on page navigation.
5. **Debounced Client Filtering**: Use 250ms debouncing for all frontend search inputs.

---

## 📝 Prompt Generation Blueprint

Whenever requested to generate a prompt for a new feature or optimization, use this exact token-lean format:

```markdown
### TASK: [Brief Title]

#### TARGET FILES:
- `[file_path]` (lines [start]-[end])

#### DATABASE SCHEMA & PROJECTION:
- Collection: `[collection_name]`
- Projection: `{"field1": 1, "field2": 1}`
- Query Constraint: `[index / regex condition]`

#### LEAN EXECUTION STEPS:
1. Modify `[file_path]`: [1-line exact instruction]
2. Verify: Run `pytest tests/[test_file].py`
```
