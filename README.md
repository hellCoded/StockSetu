# Python & MongoDB Inventory Management Web Application

A full-stack Python web application built using **Flask**, **Jinja2**, and **MongoDB** for centralized inventory tracking, stock operations, role-based authorization, and real-time dashboard analytics.

---

## Key Features

- **Full-Stack Python Architecture**: Server-side rendered HTML using Jinja2 templates, Flask route controllers, modular service layer, and MongoDB database persistence.
- **`product_name` Primary Business Identifier**: Clean product name normalization, server-side duplicate prevention, unique MongoDB index, and Admin-only product identifier renaming with complete transaction history re-linking.
- **Atomic Stock Safeguards**: Race-condition safe atomic stock operations (`$inc` query constraints) preventing negative inventory. Supports `INITIAL_STOCK`, `STOCK_IN`, `STOCK_OUT`, `ADJUSTMENT`, and `PRODUCT_RENAME` transaction logging.
- **Role-Based Access Control (RBAC)**:
  - **Admin**: Full access including user management, role assignments, account activation, product creation, editing, stock operations, and product renaming.
  - **Inventory Manager**: Product creation, editing, stock-in, stock-out, manual stock count adjustments, and transaction reporting.
  - **Staff**: View & search products, perform permitted stock-in and stock-out operations.
- **Dynamic Stock Status Tracking**:
  - `IN STOCK`: Stock quantity > minimum stock threshold.
  - `LOW STOCK`: 0 < stock quantity <= minimum stock threshold.
  - `OUT OF STOCK`: Stock quantity == 0.
- **Modern UI & Aesthetics**: Dark slate theme with neon glassmorphism accents, responsive metric KPI cards, status badges, filterable tables, modal dialogs, and vanilla JS client interactivity.

---

## Project Structure

```
CRUDV2/
├── config.py                 # Application configuration & env variables
├── run.py                    # Server startup script (python run.py)
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables
├── ROLES_AND_PERMISSIONS.md  # Comprehensive RBAC permissions matrix & role guide
├── inventory_app/            # Main application package
│   ├── __init__.py           # Flask App Factory & Jinja context processors
│   ├── database.py           # PyMongo setup, index initialization & admin seeding
│   ├── services/             # Core business logic layer
│   │   ├── auth_service.py
│   │   ├── product_service.py
│   │   ├── inventory_service.py
│   │   └── audit_service.py
│   ├── utils/                # Input validation, CSRF, security decorators & helpers
│   │   ├── validators.py
│   │   ├── decorators.py
│   │   └── helpers.py
│   ├── routes/               # Flask Blueprints
│   │   ├── auth_routes.py
│   │   ├── dashboard_routes.py
│   │   ├── product_routes.py
│   │   ├── inventory_routes.py
│   │   └── user_routes.py
│   ├── static/               # CSS styles & client JS
│   │   ├── css/style.css
│   │   └── js/main.js
│   └── templates/            # Jinja2 HTML templates
│       ├── base.html
│       ├── components/       # Reusable layout navbar, sidebar & flash alerts
│       ├── auth/             # Login & Registration views
│       ├── dashboard/        # Central metrics overview
│       ├── products/         # Product list, add, edit, rename & detail views
│       ├── inventory/        # Stock In, Stock Out, Adjust & Transaction log views
│       ├── users/            # Admin user management & profile views
│       └── errors/           # 404, 403, 500 pages
└── tests/                    # pytest automated test suite
    ├── conftest.py
    ├── test_auth.py
    ├── test_products.py
    ├── test_inventory.py
    └── test_roles.py
```

---

## Setup & Local Installation

### 1. Prerequisites
- **Python 3.10+**
- **MongoDB** (Local MongoDB instance or MongoDB Atlas URI). *Note: The test suite includes an automated in-memory `mongomock` fallback if a live MongoDB instance is not detected.*

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` as required:
```env
SECRET_KEY=dev-secret-key-change-in-production-123456789
MONGO_URI=mongodb://localhost:27017/inventory_db
DATABASE_NAME=inventory_db
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Web Application
```bash
python run.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.

### Default Login Credentials
On initial startup, the application auto-seeds a default administrator account:
- **Username**: `admin`
- **Password**: `Admin@123456`

---

## Running Automated Tests

Run the full pytest suite:
```bash
python -m pytest -v
```
To run tests with code coverage report:
```bash
python -m pytest --cov=inventory_app -v
```

---

## Deploying to Vercel (serverless)

Vercel is a serverless host — your Flask app runs as a **single catch-all function**
(`api/index.py`) with all routes proxied through `vercel.json`. It is great for a
quick, cost-free demo, but it is not an always-on server: expect cold-start latency
on idle instances.

### 1. MongoDB Atlas (free M0)

1. Create a free cluster at https://www.mongodb.com/atlas.
2. Database Access → create a user (e.g. `stocksetu`) with a strong password.
3. Network Access → **Allow access from anywhere** (`0.0.0.0/0`) so serverless
   function IPs can connect.
4. Database → Connect → Drivers → copy the connection string, e.g.
   `mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority`.
   Replace the database segment with your DB name (e.g. `/inventory_db`).

### 2. Set environment variables in Vercel

In your project → **Settings → Environment Variables**, add:

| Key            | Value                                                              |
|----------------|--------------------------------------------------------------------|
| `MONGO_URI`    | Your Atlas `mongodb+srv://...` connection string                   |
| `DATABASE_NAME`| e.g. `inventory_db`                                                 |
| `SECRET_KEY`   | A long random string (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `SESSION_COOKIE_SECURE` | `True` (Vercel serves HTTPS)                               |

> **Important:** `SESSION_COOKIE_SECURE` only takes effect on a fresh deploy after
> the env var is added — redeploy after setting it.

### 3. Deploy

**Option A — Vercel CLI**
```bash
npx vercel --prod
```

**Option B — Git import**
1. Push this repo to GitHub.
2. https://vercel.com/new → Import the repo → Framework preset **Other / Flask**.
3. Add the env vars above → Deploy.

The first deploy creates indexes on Atlas and seeds the default admin account.

### 4. After deploying

- Log in with the seeded default: **`admin` / `Admin@123456`** and **change the
  password immediately**.
- Your URL will be `https://<project>.vercel.app`.

### Production-safety notes (why this works)

- **No silent mock fallback.** `database.py` raises a clear error if Atlas is
  unreachable instead of silently switching to an empty in-memory DB. Set
  `MOCK_MONGO=1` only if you intentionally want volatile local testing.
- All exports (Excel/PDF) are generated in memory (`io.BytesIO`) — no writable
  filesystem is needed.
- Sessions are client-side signed cookies, so ephemeral serverless instances
  don't drop logins.
- `reportlab`, missing from the root requirements before, is now declared — the
  PDF export imports it at module load, so a missing package would take down the
  whole app.

> **Prefer a real always-on host?** Render or Railway run the same repo as a
> long-lived server (`gunicorn run:app`) with zero cold starts. The `api/`
> and `vercel.json` files are inert under those hosts — just use
> `pip install -r requirements.txt` and point the web process at `run.py`.
