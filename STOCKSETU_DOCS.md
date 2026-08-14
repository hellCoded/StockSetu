# StockSetu — Complete Documentation

> **Inventory Management & Billing System** built with Flask, MongoDB, and vanilla JS.
> Deployed on Vercel as a serverless application.

---

## Table of Contents

1. [What is StockSetu?](#1-what-is-stocksetu)
2. [Quick Start](#2-quick-start)
3. [Architecture Overview](#3-architecture-overview)
4. [Project Structure](#4-project-structure)
5. [Features](#5-features)
6. [User Roles & Permissions](#6-user-roles--permissions)
7. [Authentication System](#7-authentication-system)
8. [Database Schema](#8-database-schema)
9. [Core Workflows](#9-core-workflows)
10. [API Routes Reference](#10-api-routes-reference)
11. [Services Layer](#11-services-layer)
12. [Frontend & UI](#12-frontend--ui)
13. [Deployment](#13-deployment)
14. [Configuration](#14-configuration)
15. [Testing](#15-testing)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. What is StockSetu?

StockSetu is a **web-based inventory management and billing system** designed for small-to-medium businesses in India. It handles:

- **Product catalog** — create, search, categorize, and track products
- **Stock management** — stock-in, stock-out, adjustments, bulk import from supplier bills
- **GST billing** — full Indian GST compliance (CGST/SGST), HSN codes, GSTIN validation
- **Point of Sale (POS)** — quick billing interface with cart, discounts, split payments
- **User management** — role-based access control with promotion workflow
- **Reporting** — Excel/PDF exports, dashboard with charts, reconciliation reports

**Tech stack:** Python 3 / Flask 3 / MongoDB / Jinja2 / Vanilla JS / Chart.js / Vercel

---

## 2. Quick Start

### Prerequisites
- Python 3.10+
- MongoDB (local or Atlas)
- Git

### Local Setup

```bash
# Clone the repo
git clone https://github.com/hellCoded/StockSetu.git
cd StockSetu

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo SECRET_KEY=your-secret-key > .env
echo MONGO_URI=mongodb://localhost:27017/inventory_db >> .env
echo DATABASE_NAME=inventory_db >> .env

# Run the app
python run.py
```

Open `http://localhost:5000`. Login with:
- **Username:** `admin`
- **Password:** `Admin@123456`

### First Time Setup
On first run, the app automatically:
1. Creates all MongoDB indexes
2. Seeds a default admin user if none exists

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    CLIENT (Browser)                  │
│  Jinja2 Templates + Vanilla JS + Chart.js           │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (Form POST / GET)
                       ▼
┌─────────────────────────────────────────────────────┐
│              FLASK APPLICATION (api/index.py)        │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Routes   │→│ Services │→│    Database (DB)   │  │
│  │ (5 blue- │  │ (7 files)│  │   (MongoDB)       │  │
│  │  prints) │  │          │  │                    │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│       │              │              │                │
│       ▼              ▼              ▼                │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Decorators│  │  Utils   │  │    Cache Layer    │  │
│  │ auth, CSRF│  │ validate │  │ Upstash/Redis/   │  │
│  │ roles     │  │ format   │  │ Dict fallback     │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  MongoDB (8     │
              │  collections)   │
              └─────────────────┘
```

### Request Flow
1. User clicks a link or submits a form → HTTP request to Flask
2. **Decorators** check: Is the user logged in? Do they have the right role? Is the CSRF token valid?
3. **Routes** handle the request: parse inputs, call services, prepare template data
4. **Services** contain all business logic: compute taxes, validate data, interact with DB
5. **Database** stores/retrieves data from MongoDB
6. **Cache** (Upstash Redis / redislite / dict) speeds up frequent reads
7. **Template** renders the HTML response and sends it back to the browser

---

## 4. Project Structure

```
StockSetu/
├── api/
│   └── index.py              # Vercel serverless entrypoint
├── inventory_app/
│   ├── __init__.py           # App factory + cache layer
│   ├── database.py           # MongoDB connection + index creation
│   ├── routes/               # 5 Flask blueprints
│   │   ├── auth_routes.py    # Login, register, logout
│   │   ├── dashboard_routes.py
│   │   ├── product_routes.py
│   │   ├── inventory_routes.py
│   │   ├── user_routes.py
│   │   └── billing_routes.py
│   ├── services/             # Business logic
│   │   ├── auth_service.py
│   │   ├── product_service.py
│   │   ├── inventory_service.py
│   │   ├── billing_service.py
│   │   ├── audit_service.py
│   │   ├── export_service.py
│   │   └── import_service.py
│   ├── utils/                # Helpers
│   │   ├── decorators.py     # @login_required, @roles_required, @csrf_protected
│   │   ├── validators.py     # Input validation, CSRF tokens
│   │   └── helpers.py        # Stock status, currency formatting
│   ├── templates/            # 27 Jinja2 templates
│   └── static/               # CSS, JS, images
├── scripts/
│   └── seed_dummy_data.py    # Test data seeder
├── tests/                    # 9 test files (~1168 lines)
├── config.py                 # Flask configuration
├── run.py                    # Local dev entry point
├── requirements.txt          # Python dependencies
└── vercel.json               # Vercel deployment config
```

---

## 5. Features

### Inventory Management
| Feature | Description |
|---------|-------------|
| Product CRUD | Create, view, edit, rename, soft-delete products |
| Stock In | Add quantity with reason; atomic increment |
| Stock Out | Remove quantity; prevents overselling via atomic conditional update |
| Manual Adjust | Set absolute quantity; mandatory reason |
| Bulk Import | Upload supplier PDF/Excel bills → auto-parse → stock-in multiple items |
| Stock Status | Auto-calculated: IN STOCK (>5), LOW STOCK (1-5), OUT OF STOCK (0) |
| Transaction Log | Every stock change recorded with before/after, performer, reason, timestamp |
| Search & Filter | Server-side regex search + category/location/status filters |
| Rename | Admin-only; cascades to all transaction records |

### Billing / POS
| Feature | Description |
|---------|-------------|
| GST Invoice | Full Indian GST: CGST + SGST split, HSN codes, GSTIN validation |
| Invoice Numbers | Sequential: `INV/FY-YY/NNNN` (e.g., `INV/2026-27/0001`) |
| Line Discounts | Per-item discount percentage |
| Bill Discount | Bill-wide discount percentage |
| Free Items | Mark items as FREE (100% discount) |
| Extra Charges | Shipping + packing charges |
| Round-Off | Auto round to nearest rupee |
| Split Payment | Multiple methods per bill (Cash + UPI + Card) |
| Payment Tracking | PAID / PARTIAL / DUE status; record payments over time |
| Credit Sales | CREDIT method with mandatory due date |
| Bill Editing | Modify items/charges; auto stock delta computation |
| Full Refund | Restore all stock, mark bill as refunded |
| Partial Refund | Refund specific lines only |
| Reconciliation | Admin report: cross-checks invoices vs transactions vs audit logs |
| Amount in Words | Indian numbering (Lakhs/Crores) |

### User Management
| Feature | Description |
|---------|-------------|
| Self-Registration | New users register as `staff` |
| Admin Creation | Admin creates users with any role; shows credentials in modal |
| Role Promotion | Users request → admin approves/rejects → all audit-logged |
| Profile Management | Update name/email, change password |
| Account Toggle | Activate/deactivate users |

### Dashboard
| Feature | Description |
|---------|-------------|
| KPI Cards | Products, stock qty, inventory value, low/out-of-stock, today's sales, outstanding |
| Bar Chart | Stock by category (Chart.js) |
| Donut Chart | Role requests by status |
| Recent Transactions | Last 10 inventory changes |
| Billing Summary | Today's bills, total revenue, outstanding dues |

### Reports & Export
| Feature | Description |
|---------|-------------|
| Product Report | Excel/PDF with styled formatting, status badges, summary |
| Transaction Report | Excel/PDF with color-coded types |
| A4 Landscape | Professional format with headers, page numbers |

---

## 6. User Roles & Permissions

| Action | Admin | Inventory Manager | Staff |
|--------|:-----:|:-----------------:|:-----:|
| View Dashboard | ✅ | ✅ | ✅ |
| View Products | ✅ | ✅ | ✅ |
| Add/Edit Product | ✅ | ✅ | ❌ |
| Rename Product | ✅ | ❌ | ❌ |
| Toggle Product Active | ✅ | ✅ | ❌ |
| Stock In / Out | ✅ | ✅ | ✅ |
| Manual Adjust | ✅ | ✅ | ❌ |
| Bulk Import | ✅ | ✅ | ❌ |
| POS Billing | ✅ | ✅ | ✅ |
| Create Invoice | ✅ | ✅ | ✅ |
| Record Payment | ✅ | ✅ | ✅ |
| Refund Bill | ✅ | ✅ | ❌ |
| Edit Bill | ✅ | ✅ | ❌ |
| View Reconciliation | ✅ | ❌ | ❌ |
| Manage Users | ✅ | ❌ | ❌ |
| Create Users | ✅ | ❌ | ❌ |
| Change Roles | ✅ | ❌ | ❌ |
| Process Role Requests | ✅ | ❌ | ❌ |
| Export Reports | ✅ | ✅ | ❌ |

---

## 7. Authentication System

### How It Works

```
Login Request Flow:

  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
  │ /login   │───→│ Find user │───→│ Verify  │───→│ Set      │
  │ (POST)   │    │ by name/ │    │ password│    │ session  │
  │          │    │ email    │    │ hash    │    │ cookies  │
  └─────────┘    └──────────┘    └─────────┘    └──────────┘
                                       │              │
                                  wrong password    redirect to
                                  → flash error     ?next= or /
```

### Session Storage
Flask sessions (signed cookies) store:
- `user_id` — MongoDB ObjectId string
- `username` — login identifier
- `email` — user email
- `role` — admin / inventory_manager / staff

Session lifetime: **24 hours**. Cookies: HTTPOnly, SameSite=Lax, Secure.

### Password Security
- Passwords hashed with Werkzeug's `generate_password_hash()` (pbkdf2:sha256)
- Never stored in plain text
- Verified with `check_password_hash()`

### CSRF Protection
Every POST request requires a `csrf_token`:
1. Token generated via `secrets.token_hex(32)` on first visit
2. Stored in session
3. Injected into every form via `{{ csrf_token() }}`
4. Validated on every POST — rejected if missing or mismatched

### Role Enforcement
Three decorators protect routes:
```python
@login_required          # Must be logged in
@roles_required('admin') # Must have specific role
@csrf_protected          # Valid CSRF token required
```

### Emergency Admin Reset
If locked out, visit: `/reset-admin?key=<SECRET_KEY>`
Resets admin password to `Admin@123456`.

---

## 8. Database Schema

### MongoDB Collections (8 total)

#### `users`
```
{
  _id: ObjectId,
  username: String (unique, indexed),
  name: String,
  email: String (unique, indexed),
  password_hash: String,
  role: "admin" | "inventory_manager" | "staff",
  is_active: Boolean,
  created_at: DateTime,
  updated_at: DateTime
}
```

#### `products`
```
{
  _id: ObjectId,
  product_name: String (unique, indexed),
  category: String (indexed),
  description: String,
  quantity: Float,
  unit: String,              // pcs, bags, meters, liters, etc.
  price: Float,              // INR per unit
  gst_rate: Float,           // 0-28%
  hsn_code: String,          // max 8 chars
  minimum_stock: 5,          // hardcoded threshold
  location: String (indexed),
  is_active: Boolean (indexed),
  created_at: DateTime,
  updated_at: DateTime
}
```

#### `inventory_transactions`
```
{
  _id: ObjectId,
  product_name: String (indexed),
  transaction_type: String (indexed),
    // INITIAL_STOCK, STOCK_IN, STOCK_OUT, ADJUSTMENT,
    // BILL_SALE, BILL_REFUND, PRODUCT_RENAME
  quantity: Float,           // delta (can be negative for stock-out)
  previous_quantity: Float,
  new_quantity: Float,
  reason: String,
  performed_by: String,
  created_at: DateTime (indexed, desc),
  metadata: Object           // optional extra data
}
```

#### `invoices`
```
{
  _id: ObjectId,
  bill_number: String (unique),   // INV/FY-YY/NNNN
  customer_name: String (indexed),
  customer_phone: String,
  customer_gstin: String,
  payment_method: "CASH" | "UPI" | "CARD" | "CREDIT",
  payment_status: "PAID" | "PARTIAL" | "DUE" | "REFUNDED",
  line_items: [{
    product_name, hsn_code, quantity, unit_price,
    line_discount_percent, line_discount_amount,
    raw_taxable, taxable, gst_rate, gst_amount,
    cgst, sgst, line_total, is_free,
    is_refunded, refund_quantity
  }],
  subtotal: Float,
  total_line_discount: Float,
  discount_percent: Float,
  discount_amount: Float,
  cgst_total: Float,
  sgst_total: Float,
  gst_total: Float,
  free_total: Float,
  shipping_charge: Float,
  packing_charge: Float,
  charges_total: Float,
  round_off: Float,
  grand_total: Float,
  amount_paid: Float,
  amount_due: Float,
  due_date: DateTime,          // for CREDIT
  refunded_at: DateTime,
  refunded_by: String,
  refund_reason: String,
  refund_history: [{}],
  edit_history: [{}],
  created_by: String (indexed),
  created_at: DateTime (indexed, desc)
}
```

#### `bill_payments`
```
{
  _id: ObjectId,
  bill_id: ObjectId (indexed),
  bill_number: String (indexed),
  amount: Float,
  method: String,
  reference: String,
  performed_by: String,
  created_at: DateTime
}
```

#### `audit_logs`
```
{
  _id: ObjectId,
  action_type: String,
  performed_by: String,
  target_resource: String (indexed),
  details: Object,
  created_at: DateTime (indexed, desc)
}
```

#### `role_requests`
```
{
  _id: ObjectId,
  user_id: String,
  username: String,
  email: String,
  current_role: String,
  requested_role: String,
  reason: String,
  status: "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED",
  processed_by: String,
  admin_comment: String,
  created_at: DateTime,
  updated_at: DateTime
}
```

#### `bill_counters`
```
{
  _id: "invoice_seq",
  seq: Integer               // auto-incrementing invoice number
}
```

---

## 9. Core Workflows

### 9.1 Product Creation

```
User fills form → POST /products/add
       │
       ▼
product_service.create_product()
       │
       ├── Validate: name length, price ≥ 0, GST 0-28%, HSN ≤ 8 chars
       ├── Check: product_name unique (case-insensitive)
       ├── Insert into `products` collection
       ├── Record INITIAL_STOCK transaction in `inventory_transactions`
       ├── Log audit: PRODUCT_CREATE
       └── Invalidate product cache
```

### 9.2 Stock Out (Prevents Overselling)

```
User submits stock-out → POST /inventory/stock-out
       │
       ▼
inventory_service.stock_out()
       │
       ├── Validate: quantity > 0
       ├── Atomic DB update:
       │   db.products.update_one(
       │     { product_name: name, quantity: { $gte: quantity } },
       │     { $inc: { quantity: -quantity } }
       │   )
       │   └── If matched_count == 0 → "Insufficient stock" error
       ├── Record STOCK_OUT transaction
       └── Log audit: STOCK_OUT
```

The `$gte` check is **atomic** — prevents race conditions where two users try to stock-out the same last unit simultaneously.

### 9.3 Bill Creation (GST Invoice)

```
User builds cart → POST /billing/create
       │
       ▼
billing_service.create_bill()
       │
       ├── 1. Resolve products from DB
       ├── 2. Compute bill (compute_bill):
       │   ├── Per line: raw_taxable = price × qty
       │   ├── Line discount: disc_amt = raw_taxable × disc% / 100
       │   ├── Taxable = raw_taxable - disc_amt
       │   ├── GST = taxable × gst_rate / 100
       │   ├── CGST = GST / 2, SGST = GST / 2
       │   ├── Bill-level discount on subtotal
       │   ├── Add shipping + packing charges
       │   ├── Round off to nearest rupee
       │   └── Determine payment status (PAID/PARTIAL/DUE)
       ├── 3. Generate bill number: INV/FY-YY/NNNN (atomic counter)
       ├── 4. Atomically deduct stock for ALL items:
       │   ├── Attempt each deduction
       │   ├── If ANY fails → rollback all previous deductions
       │   └── Return error with list of insufficient items
       ├── 5. Insert into `invoices`
       ├── 6. Insert into `bill_payments` (if partial/full payment)
       └── 7. Log audit: BILL_CREATE with full snapshot
```

### 9.4 Bill Refund

```
Admin clicks refund → POST /billing/bills/<id>/refund
       │
       ▼
billing_service.refund_bill()
       │
       ├── For each line item:
       │   ├── Restore stock: quantity += refund_quantity
       │   ├── Record BILL_REFUND transaction
       │   └── Mark line as is_refunded = true
       ├── Update invoice: payment_status = "REFUNDED"
       ├── Store refund_history entry
       └── Log audit: BILL_REFUND
```

### 9.5 Role Promotion Workflow

```
User requests promotion → POST /request-promotion
       │
       ├── Check: no existing PENDING request
       ├── Create role_request (status: PENDING)
       └── Log audit

Admin reviews → POST /users/requests/<id>/approve
       │
       ├── Update role_request status to APPROVED
       ├── Change user's role in `users` collection
       └── Log audit
```

---

## 10. API Routes Reference

### Auth (`/login`, `/register`, `/logout`, `/reset-admin`)
| Route | Method | Auth | Role | Description |
|-------|--------|------|------|-------------|
| `/login` | GET, POST | No | — | Login page |
| `/register` | GET, POST | No | — | Self-registration (staff) |
| `/logout` | GET | Yes | Any | Clear session |
| `/reset-admin?key=<key>` | GET | No | — | Emergency admin reset |

### Dashboard (`/`)
| Route | Method | Auth | Role | Description |
|-------|--------|------|------|-------------|
| `/` | GET | Yes | Any | Dashboard with KPIs + charts |

### Products (`/products`)
| Route | Method | Auth | Role | Description |
|-------|--------|------|------|-------------|
| `/products` | GET | Yes | Any | Product list with search/filter |
| `/products/add` | GET, POST | Yes | admin, manager | Add product |
| `/products/<name>` | GET | Yes | Any | Product detail |
| `/products/<name>/edit` | GET, POST | Yes | admin, manager | Edit product |
| `/products/<name>/rename` | GET, POST | Yes | admin | Rename product |
| `/products/<name>/toggle-active` | POST | Yes | admin, manager | Toggle active |
| `/products/export/excel` | GET | Yes | admin, manager | Excel export |
| `/products/export/pdf` | GET | Yes | admin, manager | PDF export |

### Inventory (`/inventory`, `/products/<name>/stock-*`)
| Route | Method | Auth | Role | Description |
|-------|--------|------|------|-------------|
| `/inventory/stock-in` | GET, POST | Yes | Any | Stock-in form |
| `/products/<name>/stock-in` | GET, POST | Yes | Any | Pre-selected stock-in |
| `/inventory/stock-out` | GET, POST | Yes | Any | Stock-out form |
| `/products/<name>/stock-out` | GET, POST | Yes | Any | Pre-selected stock-out |
| `/inventory/adjust` | GET, POST | Yes | admin, manager | Stock adjustment |
| `/products/<name>/adjust` | GET, POST | Yes | admin, manager | Pre-selected adjust |
| `/inventory/bulk-stock-in` | GET, POST | Yes | admin, manager | Upload supplier bill |
| `/inventory/bulk-stock-in/confirm` | POST | Yes | admin, manager | Confirm bulk import |
| `/transactions` | GET | Yes | Any | Transaction log |
| `/transactions/export/excel` | GET | Yes | admin, manager | Export transactions |
| `/transactions/export/pdf` | GET | Yes | admin, manager | Export transactions |

### Billing (`/billing`)
| Route | Method | Auth | Role | Description |
|-------|--------|------|------|-------------|
| `/billing` | GET | Yes | Any | POS screen |
| `/billing/create` | POST | Yes | Any | Create invoice |
| `/billing/bills` | GET | Yes | Any | Bill history |
| `/billing/bills/<id>` | GET | Yes | Any | Bill detail |
| `/billing/bills/<id>/refund` | POST | Yes | admin, manager | Full refund |
| `/billing/bills/<id>/refund-lines` | POST | Yes | admin, manager | Partial refund |
| `/billing/bills/<id>/pay` | POST | Yes | Any | Record payment |
| `/billing/bills/<id>/edit` | POST | Yes | admin, manager | Edit bill |
| `/health` | GET | No | — | Health check (keep-warm) |

### Users (`/users`, `/profile`)
| Route | Method | Auth | Role | Description |
|-------|--------|------|------|-------------|
| `/users` | GET | Yes | admin | User management |
| `/users/add` | POST | Yes | admin | Create user |
| `/users/<id>/role` | POST | Yes | admin | Change role |
| `/users/<id>/toggle-active` | POST | Yes | admin | Toggle active |
| `/request-promotion` | POST | Yes | Any | Request promotion |
| `/users/requests/<id>/approve` | POST | Yes | admin | Approve request |
| `/users/requests/<id>/reject` | POST | Yes | admin | Reject request |
| `/requests/<id>/cancel` | POST | Yes | Any | Cancel own request |
| `/profile` | GET, POST | Yes | Any | Edit profile |

---

## 11. Services Layer

### auth_service.py — User Management
| Function | Purpose |
|----------|---------|
| `register_user()` | Create new user with validation |
| `authenticate_user()` | Verify credentials, set session |
| `get_all_users()` | List all users |
| `update_user_role()` | Change user role |
| `toggle_user_active()` | Activate/deactivate |
| `change_password()` | Verify old + set new |
| `create_role_request()` | Submit promotion request |
| `process_role_request()` | Admin approve/reject |

### product_service.py — Product Operations
| Function | Purpose |
|----------|---------|
| `create_product()` | Create with validation + audit |
| `get_product_by_name()` | Cached lookup (30s TTL) |
| `search_products()` | Regex search + filters |
| `update_product()` | Edit with validation |
| `rename_product()` | Admin rename + cascade |
| `get_stock_by_category()` | Aggregation for charts |

### inventory_service.py — Stock Operations
| Function | Purpose |
|----------|---------|
| `stock_in()` | Atomic `$inc` + transaction log |
| `stock_out()` | Atomic conditional `$gte` + transaction log |
| `stock_adjust()` | Set absolute quantity + mandatory reason |
| `get_dashboard_metrics()` | KPI computations |

### billing_service.py — Invoice System (largest: 1163 lines)
| Function | Purpose |
|----------|---------|
| `compute_line()` | Single line tax/discount calc |
| `compute_bill()` | Full bill computation |
| `create_bill()` | Create invoice with stock deduction + rollback |
| `edit_bill()` | Modify bill + stock delta |
| `refund_bill()` | Full refund + stock restore |
| `refund_bill_lines()` | Partial line refund |
| `record_bill_payment()` | Add payment record |
| `get_reconciliation_report()` | Anomaly detection |

### export_service.py — Report Generation
| Function | Purpose |
|----------|---------|
| `generate_excel_export()` | Styled .xlsx with KPIs |
| `generate_pdf_export()` | A4 landscape PDF with tables |

### import_service.py — Supplier Bill Parsing
| Function | Purpose |
|----------|---------|
| `parse_supplier_bill()` | Route to PDF/Excel parser |
| `_parse_pdf()` | pdfplumber table extraction |
| `_parse_excel()` | openpyxl data extraction |

---

## 12. Frontend & UI

### Design System (CSS Custom Properties)
```css
:root {
  /* Colors */
  --primary: #4f46e5;        /* Indigo */
  --success: #10b981;        /* Green */
  --warning: #f59e0b;        /* Amber */
  --danger: #ef4444;         /* Red */
  
  /* Brand */
  --jklc-red: #E4132B;
  --jklc-blue: #0B3D6E;
  --jklc-gold: #C9A24B;
  
  /* Typography */
  --font-body: 'Inter';
  --font-display: 'Plus Jakarta Sans';
  
  /* Shadows */
  --shadow-xs through --shadow-xl;
  
  /* Border Radius */
  --r-xs through --r-full;
}
```

### JavaScript Architecture
| File | Purpose |
|------|---------|
| `main.js` | Core UI: modals, toasts, KPI animation, sortable tables, search, form autosave |
| `dashboard.js` | Chart.js rendering, skeleton loading |
| `toasts.js` | Auto-dismissing notifications |
| POS (inline in `pos.html`) | Cart management, GST calculation, payment handling |

### Key UI Features
- **Dark Mode** — toggle via `data-theme="dark"`, persisted in localStorage
- **Responsive** — mobile-first with collapsible sidebar
- **Toast Notifications** — replaces flash messages
- **Live Stock Preview** — real-time projected quantity on stock forms
- **Sortable Tables** — click any column header
- **KPI Counter Animation** — smooth count-up on dashboard
- **Custom Confirm Modal** — replaces browser `confirm()`
- **Skeleton Loaders** — loading states for async content
- **Print Styles** — clean invoice printing

---

## 13. Deployment

### Vercel Configuration
```json
{
  "version": 2,
  "functions": {
    "api/index.py": {
      "maxDuration": 30,
      "memory": 1024
    }
  },
  "routes": [
    { "src": "/(.*)", "dest": "/api/index" }
  ]
}
```

- All requests routed to `api/index.py` (single serverless function)
- 30s timeout, 1024MB memory
- No cron (Hobby plan restriction)

### Caching Strategy (Serverless)
```
Request → Check Cache
            │
            ├── HIT → Return cached data
            │
            └── MISS → Query MongoDB → Cache result → Return
```

| Layer | Technology | Fallback |
|-------|-----------|----------|
| Primary | Upstash Redis (REST API) | — |
| Secondary | redislite (in-process) | — |
| Tertiary | Python dict (per-instance) | — |

Cache TTLs: Products 30s, Dashboard 30s, Billing 60s, Role requests 30s.

### Keep-Warm
- External uptime monitor (UptimeRobot/cron-job.org) pings `/health` every 5 min
- `/health` returns `"OK"` without DB access — instant, cheap
- Prevents serverless function from sleeping between requests

### Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | fallback key | Flask session signing |
| `MONGO_URI` | Yes | localhost | MongoDB connection string |
| `DATABASE_NAME` | Yes | inventory_db | Database name |
| `UPSTASH_REDIS_REST_URL` | No | — | Redis cache endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | No | — | Redis auth token |
| `SESSION_COOKIE_SECURE` | No | True | HTTPS-only cookies |
| `MOCK_MONGO` | No | — | Force mongomock (testing) |

---

## 14. Configuration

### config.py
```python
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'inventory-super-secret-key-2026-safe')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/inventory_db')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'inventory_db')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

class TestConfig(Config):
    TESTING = True
    DATABASE_NAME = 'inventory_test_db'
```

### Rate Limiting
- **Default:** 200 requests/minute, 50/second (Flask-Limiter)
- **Billing routes:** Additional sliding-window limiter: 60 requests/minute per IP

---

## 15. Testing

### Run Tests
```bash
pytest tests/ -v
```

### Test Framework
- **pytest** with **mongomock** (in-memory MongoDB)
- 3 pre-seeded test users: `testadmin`, `testmanager`, `teststaff`
- Pre-authenticated test clients for each role

### Test Coverage
| File | Tests | What's Tested |
|------|-------|---------------|
| `test_auth.py` | 8 | Login, register, logout, profile, password |
| `test_products.py` | 8 | CRUD, search, export, charts |
| `test_inventory.py` | 5 | Stock in/out/adjust, status transitions |
| `test_billing.py` | 7 | Invoice creation, GST, stock deduction, validation |
| `test_import.py` | 7 | Supplier bill parsing (Excel) |
| `test_bulk_import.py` | 7 | Bulk import confirm flow |
| `test_roles.py` | 9 | RBAC, promotion workflow |
| `test_seed_data.py` | 2 | Data seeder idempotency |
| `test_features.py` | 1 | Discount + refund integration |

---

## 16. Troubleshooting

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Deploy blocked on Vercel | Invalid `vercel.json` (cron too frequent) | Remove cron or use `0 0 * * *` |
| App slow on first visit | Serverless cold start | Set up external uptime monitor pinging `/health` |
| "Insufficient stock" on bill | Stock-out quantity > available | Check stock levels in product detail |
| Session expired | 24-hour timeout | Re-login |
| MongoDB connection error | Wrong `MONGO_URI` or MongoDB not running | Check `.env` and MongoDB service |
| CSRF error | Token mismatch (page stale) | Refresh page and resubmit |
| Admin locked out | Forgot password | Visit `/reset-admin?key=<SECRET_KEY>` |

### Useful Commands
```bash
# Check deployment status
git log --oneline -5

# Run tests
pytest tests/ -v

# Seed test data
python scripts/seed_dummy_data.py --count 50

# Clean seeded data
python scripts/seed_dummy_data.py --clean

# Force seed in production
python scripts/seed_dummy_data.py --force
```

---

*Documentation generated for StockSetu — a Flask + MongoDB inventory management and billing system.*
