# StockSetu — Codebase Audit Summary

**Date:** 2026-08-12  
**Project:** Flask + MongoDB inventory/POS for JK Lakshmi Cement  
**Scope:** Read-only audit — no modifications made

---

## 1. All Registered Routes (by Blueprint)

| Blueprint | Route | Methods | File | Line |
|-----------|-------|---------|------|------|
| **auth** (`auth_bp`) | `/login` | GET, POST | `inventory_app/routes/auth_routes.py` | 8 |
| | `/register` | GET, POST | `inventory_app/routes/auth_routes.py` | 42 |
| | `/logout` | GET | `inventory_app/routes/auth_routes.py` | 85 |
| **dashboard** (`dashboard_bp`) | `/` | GET | `inventory_app/routes/dashboard_routes.py` | 13 |
| | `/dashboard` | GET | `inventory_app/routes/dashboard_routes.py` | 14 |
| **products** (`product_bp`) | `/products` | GET | `inventory_app/routes/product_routes.py` | 12 |
| | `/products/export/excel` | GET | `inventory_app/routes/product_routes.py` | 46 |
| | `/products/export/pdf` | GET | `inventory_app/routes/product_routes.py` | 130 |
| | `/products/add` | GET, POST | `inventory_app/routes/product_routes.py` | 240 |
| | `/products/<product_name>` | GET | `inventory_app/routes/product_routes.py` | 273 |
| | `/products/<product_name>/edit` | GET, POST | `inventory_app/routes/product_routes.py` | 284 |
| | `/products/<product_name>/rename` | GET, POST | `inventory_app/routes/product_routes.py` | 320 |
| | `/products/<product_name>/toggle-active` | POST | `inventory_app/routes/product_routes.py` | 344 |
| **inventory** (`inventory_bp`) | `/inventory/stock-in` | GET, POST | `inventory_app/routes/inventory_routes.py` | 10 |
| | `/products/<product_name>/stock-in` | GET, POST | `inventory_app/routes/inventory_routes.py` | 11 |
| | `/inventory/stock-out` | GET, POST | `inventory_app/routes/inventory_routes.py` | 38 |
| | `/products/<product_name>/stock-out` | GET, POST | `inventory_app/routes/inventory_routes.py` | 39 |
| | `/inventory/adjust` | GET, POST | `inventory_app/routes/inventory_routes.py` | 66 |
| | `/products/<product_name>/adjust` | GET, POST | `inventory_app/routes/inventory_routes.py` | 67 |
| | `/transactions` | GET | `inventory_app/routes/inventory_routes.py` | 94 |
| | `/transactions/export/excel` | GET | `inventory_app/routes/inventory_routes.py` | 108 |
| | `/transactions/export/pdf` | GET | `inventory_app/routes/inventory_routes.py` | 179 |
| **billing** (`billing_bp`) | `/billing` | GET | `inventory_app/routes/billing_routes.py` | 8 |
| | `/billing/create` | POST | `inventory_app/routes/billing_routes.py` | 25 |
| | `/billing/bills` | GET | `inventory_app/routes/billing_routes.py` | 56 |
| | `/billing/bills/<bill_id>` | GET | `inventory_app/routes/billing_routes.py` | 63 |
| **users** (`user_bp`) | `/users` | GET | `inventory_app/routes/user_routes.py` | 12 |
| | `/users/add` | POST | `inventory_app/routes/user_routes.py` | 20 |
| | `/users/<user_id>/role` | POST | `inventory_app/routes/user_routes.py` | 72 |
| | `/users/<user_id>/toggle-active` | POST | `inventory_app/routes/user_routes.py` | 91 |
| | `/request-promotion` | POST | `inventory_app/routes/user_routes.py` | 109 |
| | `/users/requests/<request_id>/approve` | POST | `inventory_app/routes/user_routes.py` | 131 |
| | `/users/requests/<request_id>/reject` | POST | `inventory_app/routes/user_routes.py` | 145 |
| | `/requests/<request_id>/cancel` | POST | `inventory_app/routes/user_routes.py` | 159 |
| | `/profile` | GET, POST | `inventory_app/routes/user_routes.py` | 171 |

**Total: 32 route endpoints across 6 blueprints**

---

## 2. Test Files & Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/conftest.py` | 5 fixtures | `mock_mongo`, `app`, `client`, `admin_client`, `manager_client`, `staff_client` — shared test infrastructure |
| `tests/test_auth.py` | 9 tests | Login page render, valid login, invalid password, unregistered user redirect, registration success, duplicate username, logout, profile update, password change (valid/invalid) |
| `tests/test_products.py` | 10 tests | Create product, duplicate name rejection, search/filter, edit product, rename (admin-only vs staff), toggle active, Excel export, PDF export, dashboard chart aggregations |
| `tests/test_inventory.py` | 5 tests | Stock in, stock out success, stock out insufficient stock, stock adjustment mandatory reason, status badge transitions (IN STOCK → LOW STOCK → OUT OF STOCK) |
| `tests/test_billing.py` | 9 tests | Bill creation (deducts stock, GST calc), sequential invoice numbers, insufficient stock failure, required customer name/items, invalid GSTIN rejection, bill history & detail pages, POS page renders products, GST fields on product forms |
| `tests/test_roles.py` | 9 tests | Staff restricted routes, manager allowed/restricted routes, admin full access, admin add user shows modal credentials, staff promotion request flow, manager → admin elevation, request rejection flow, validation & duplicates, cancel flow, audit logging |
| `tests/test_seed_data.py` | 2 tests | Full seed & clean workflow (100 products, 100 users, role distribution, low stock, password verification, idempotency, clean rollback), safety guard in production |

**Total: 44 tests across 7 test files**

---

## 3. Hardcoded / Seed / Mock Data Sources

| Source | Type | Contents |
|--------|------|----------|
| `scripts/seed_dummy_data.py` | **Seeder script** | 8 categories, 8 units, 100 products (`TEST-SKU-XXXX`), 100 users (`test{role}{NNN}@example.test`), fixed password `TestPass123!`, ~15% low stock, ~10% inactive users, role distribution: 5% admin, 15% manager, 80% staff |
| `tests/conftest.py` | **Test fixtures** | 3 mock users: `testadmin`/`AdminPass123` (admin), `testmanager`/`ManagerPass123` (inventory_manager), `teststaff`/`StaffPass123` (staff) |
| `tests/test_billing.py` | **Test helper** | `_seed_product()` inserts products with fixed data: "Steel Rod" (₹500, 18% GST, HSN 7214), "Item A", "Item B", "Limited Item" |
| `config.py` → `TestConfig` | **Test config** | `MONGO_URI=mongodb://localhost:27017/inventory_test_db`, `SECRET_KEY=test-secret-key` |
| `inventory_app/utils/validators.py` | **Validators** | Likely contains hardcoded validation rules (password complexity, username format, etc.) |
| `inventory_app/services/auth_service.py` | **Auth defaults** | Default role `'staff'` on registration |

---

## 4. Routes Flagged as Candidates for Removal / Review

| Route | Reason | Evidence |
|-------|--------|----------|
| `/products/export/excel` & `/products/export/pdf` | **Potential duplicate** — Same filter logic duplicated in inventory transactions export; could be consolidated into a shared export service | Both re-implement nearly identical filtering/query logic (lines 54-68 in product_routes.py vs 116-119 in inventory_routes.py) |
| `/inventory/stock-in` + `/products/<product_name>/stock-in` (dual routes) | **Duplicate endpoint pattern** — Same handler registered twice; same for stock-out and adjust | Each has 2 `@route` decorators pointing to same function; consider keeping only one canonical URL pattern |
| `/dashboard` (alias for `/`) | **Redundant alias** — Root `/` already serves dashboard; `/dashboard` adds no value | Both map to `dashboard.index()`; could remove `/dashboard` |
| `/users/requests/<request_id>/approve` & `/users/requests/<request_id>/reject` | **Could be unified** — Same pattern, different action; could use single endpoint with `action` param | Separate routes for approve/reject with nearly identical logic |

---

## Additional Observations

- **No `/test`, `/debug`, `/ping-old` routes found** — good hygiene
- **All routes have frontend references** — every route in sidebar/templates has a corresponding `url_for()` call
- **CSRF protection** applied consistently on all POST routes via `@csrf_protected`
- **Role-based access** enforced via `@roles_required` decorators
- **Seed data is well-contained** — prefixed with `TEST-SKU-` and `@example.test` for safe cleanup

---

*Generated by opencode audit — ready for cleanup phase when approved.*