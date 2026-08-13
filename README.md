# StockSetu

Inventory management & GST billing system for small businesses in India.

**Live:** [stocksetu.vercel.app](https://stocksetu.vercel.app)

## Features

- **Product Catalog** — add, search, categorize, track stock levels
- **Stock Management** — stock-in, stock-out, manual adjustments, bulk import from supplier bills
- **GST Billing** — full Indian GST (CGST/SGST), HSN codes, GSTIN validation, invoice generation
- **Point of Sale** — quick billing with cart, discounts, split payments, credit sales
- **Dashboard** — KPIs, charts, recent transactions at a glance
- **Reports** — export products & transactions as Excel or PDF
- **User Roles** — admin, inventory manager, staff with granular permissions
- **Dark Mode** — toggle on/off, saved per device

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| Database | MongoDB |
| Frontend | Jinja2, Vanilla JS, Chart.js |
| Styling | Custom CSS (design tokens, dark mode) |
| Deployment | Vercel (serverless) |

## Quick Start

```bash
# Clone
git clone https://github.com/hellCoded/StockSetu.git
cd StockSetu

# Install
pip install -r requirements.txt

# Setup env
cp .env.example .env   # or create manually:
# SECRET_KEY=your-secret
# MONGO_URI=mongodb://localhost:27017/inventory_db
# DATABASE_NAME=inventory_db

# Run
python run.py
```

Open **http://localhost:5000**

**Default login:** `admin` / `Admin@123456`

## Roles

| | Admin | Inventory Manager | Staff |
|---|:---:|:---:|:---:|
| View products | ✅ | ✅ | ✅ |
| Add/edit products | ✅ | ✅ | ❌ |
| Stock in/out | ✅ | ✅ | ✅ |
| POS billing | ✅ | ✅ | ✅ |
| Refund/edit bills | ✅ | ✅ | ❌ |
| Manage users | ✅ | ❌ | ❌ |
| Rename products | ✅ | ❌ | ❌ |

## Project Structure

```
StockSetu/
├── api/index.py              # Vercel entrypoint
├── inventory_app/
│   ├── routes/               # 5 Flask blueprints
│   ├── services/             # Business logic
│   ├── utils/                # Auth decorators, validators
│   ├── templates/            # 27 Jinja2 pages
│   └── static/               # CSS, JS, images
├── tests/                    # pytest suite
├── config.py
└── requirements.txt
```

## Testing

```bash
pytest tests/ -v
```

## License

Private — not for redistribution.
