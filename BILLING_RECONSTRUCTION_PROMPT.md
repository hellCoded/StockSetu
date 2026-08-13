# PROMPT: Reconstruct & Improve the Billing Algorithm (StockSetu / Inventory Hub)

Use this prompt as a work order for an AI coding agent or developer. Paste it as-is.

---

## 1. CONTEXT

You are working on **StockSetu / Inventory Hub**, a Flask + MongoDB inventory & POS
application (Python 3.12, Jinja2 templates, vanilla JS, existing pytest suite at `tests/`).

Relevant existing files:
- `inventory_app/services/billing_service.py` — billing core logic (`create_bill`,
  `_deduct_stock`, `_generate_bill_number`, `refund_bill`, `get_bills`, `get_billing_summary`)
- `inventory_app/routes/billing_routes.py` — routes: `pos`, `create`, `list_bills`,
  `view_bill`, `refund`
- `inventory_app/templates/billing/pos.html` — POS cart UI (JS cart, qty +/- buttons)
- `inventory_app/templates/billing/bills.html` — bill history table
- `inventory_app/templates/billing/bill_detail.html` — A5 invoice + 80mm thermal receipt
- `inventory_app/services/audit_service.py` — `log_audit(action_type, performed_by, target_resource, details)`
- `inventory_app/services/product_service.py` — product lookup/stock helpers
- `inventory_app/utils/validators.py`, `inventory_app/utils/decorators.py`
- MongoDB collections in use: `invoices`, `inventory_transactions`, `audit_logs`,
  `products`, `bill_counters`, `users`

Read all of these files first. Preserve the existing design system (CSS variables,
glassmorphism modals, `.btn`, `.badge`, `.data-table`, `format_currency`, `format_datetime`,
`amount_in_words`, CSRF protection, `@login_required` / `@roles_required` decorators).
Do not switch frameworks or libraries. Match the existing code style (no new comments
unless required).

## 2. GOAL

Rebuild and harden the billing engine so it supports the full set of billing scenarios
listed below, with matching UI/UX, routes, data-model changes, audit trails, and tests.
Every change must keep the system **accountant-auditable** (see section 6).

## 3. SUPPORTED SCENARIOS (must all work)

### 3.1 Sales & payment
1. Cash sale (single/multi item), UPI, Card, Credit sales.
2. **Split / partial payment**: a bill can be paid via a mix (e.g. cash + UPI), or
   partially paid (advance) with the remainder on credit.
3. **Credit bills**: `payment_status` must be `DUE`/`PARTIAL`/`PAID`, with outstanding
   amount, due date, and a **payment-received ledger** (`bill_payments` collection) so an
   accountant can trace what was collected when.
4. **Payment reference capture**: UPI transaction ID / card last-4 / cheque no (optional
   but stored when provided).
5. **Record payment against a bill** (new route + UI): mark a DUE bill fully/partially paid.
6. **Reprint** receipts (already exists) in A5 and 80mm thermal formats.

### 3.2 Line-item flexibility
7. **Item-level discount**: per-line discount percent (in addition to existing bill-level %).
8. **Free supply / zero-value lines**: allow a line with qty > 0 and discount 100% (value ₹0)
   OR explicit `is_free` flag. Such lines must be **flagged** (`free_supply: true`) and
   valued per GST Schedule-I rules for the audit trail. A line with **quantity = 0** is still
   rejected at the algorithm level (see 3.4), but free/zero-value (qty>0, value 0) is allowed.
9. **Extra charges**: optional shipping/packing/rounding charges on the bill header
   (round-off adjustable, default round to nearest 0.01 and store the round-off amount).
10. **Tax flexibility**: keep per-product `gst_rate` (0–28%). Lines with rate 0 are
    nil-rated/exempt and must be labeled as such on the invoice.

### 3.3 Returns & adjustments
11. **Partial refund / line return**: refund specific line(s) of a bill (not the whole bill).
    Restores that line's stock, records `BILL_REFUND` per line, and updates the bill's
    `payment_status`/amounts consistently.
12. **Full refund** (existing behavior) must keep working and go through the same ledger.
13. **Bill edit for corrections** (admin/inventory_manager only): edit items on a
    non-refunded bill. The algorithm must compute the stock delta (added/removed items) and
    apply it, and record an `BILL_EDIT` audit entry with before/after snapshots. This is an
    opt-in scenario — if the scope is too large, implement the audit snapshot + stock delta
    mechanics, and mark this scenario explicitly as designed-but-stubbed in your summary.

### 3.4 Invariant guards (must remain enforced)
14. `quantity <= 0` on any line → reject with a clear message (existing behavior).
15. `quantity` must be a finite number (reject `NaN`, `inf`, non-numeric).
16. Insufficient stock → reject; inactive product → reject; missing product → reject;
    invalid GSTIN → reject (existing, keep).
17. Any arithmetic invariant: `line_total == round(qty * price * (1 - discount%) , 2) + tax`,
    and bill totals must equal the sum of line totals. The algorithm must round consistently
    and record the round-off line if enabled.

## 4. ALGORITHM REQUIREMENTS (billing_service.py)

Rewrite/extend the calculation pipeline as a **pure, testable core**:
- New helper e.g. `compute_bill(customer_data, items, charges, settings) -> (ok, msg, computed)`
  that validates, computes per-line totals (taxable, discount, cgst/sgst, line_total), bill
  totals, charges, round-off, grand total, and returns a normalized bill document (no DB side
  effects). This makes the math unit-testable in isolation.
- Keep `create_bill` as the orchestrator: call `compute_bill`, then atomically:
  1. Deduct stock per line (existing `_deduct_stock` pattern, per-line `BILL_SALE`
     transaction, with full rollback on any failure).
  2. Insert `invoices` doc (include `payment_status`, `amount_paid`, `amount_due`, `due_date`,
     `payments` array or ledger refs, `line_items` with discounts, free flag, charges).
  3. Insert `bill_payments` records for any immediate payment splits.
  4. Write **immutable audit snapshot** (see section 6).
- Atomicity: any failure after stock deduction must fully roll back stock + transactions
  (existing refund-on-fail pattern must be preserved for all new paths).
- `refund_bill` and the new partial refund / record-payment functions must keep the same
  stock-restoration and ledger integrity guarantees.

## 5. ROUTES & API (billing_routes.py)

Add/modify routes (all behind `@login_required`, CSRF on POSTs, RBAC as noted):
- `POST /billing/create` — modify to accept split-payment fields, item discounts, charges,
  free-supply flags; still calls `create_bill`.
- `POST /billing/bills/<bill_id>/pay` — record a payment against a bill (staff/admin/manager).
- `POST /billing/bills/<bill_id>/refund` — keep (whole-bill).
- `POST /billing/bills/<bill_id>/refund-line` — partial/line refund
  (admin/inventory_manager).
- `POST /billing/bills/<bill_id>/edit` — bill correction (admin/inventory_manager).
- `GET /billing/bills/<bill_id>` — extend detail view to show payment ledger, dues,
  charges, free lines, and audit history.
- `GET /billing/reconciliation` (admin) — report that cross-checks `invoices` vs
  `inventory_transactions` vs `audit_logs` and flags anomalies (see section 7).
- Update `get_bills` / dashboard `get_billing_summary` to include `amount_due` totals and
  filter by payment status.

## 6. AUDIT & ACCOUNTING REQUIREMENTS (mandatory)

1. **Immutable snapshot**: every `BILL_CREATE` audit entry must store the **full line-item
   snapshot** (product, qty, rate, discount, taxable, cgst, sgst, line_total, free flag)
   plus subtotal, charges, round-off, grand total, payment split, and cashier — so the
   original state survives any later edits.
2. **Log rejected attempts**: add `BILL_CREATE_REJECTED` audit entries (action_type, staff
   member, offending item/qty, reason) whenever the algorithm rejects a submission, so
   attempted manipulation (e.g. qty=0) is visible to an accountant.
3. **Ledger events**: `BILL_PAYMENT`, `BILL_REFUND_LINE`, `BILL_EDIT`, `BILL_REFUND` audit
   entries with before/after values and performer.
4. **Reconciliation invariant** (section 7): each sale line must match a `BILL_SALE` stock
   transaction (qty ties out); each refund line must match a `BILL_REFUND` stock
   transaction; payments must tie to bill dues.
5. **GST-free supply**: free/zero-value lines are preserved in the snapshot and labeled on
   the invoice; the reconciliation report counts them separately.

## 7. RECONCILIATION / FLAGGING

The `GET /billing/reconciliation` admin report must detect and list:
- Bills where any line total != qty × price × (1 − disc%) + tax (arithmetic mismatch).
- Any stored line with quantity ≤ 0 (should never exist after this change — flag as anomaly).
- Zero-value/free lines (count + value, flagged for GST free-supply review).
- Bills whose `BILL_SALE` stock deductions do not tie to `line_items`.
- Bills with `payment_status = DUE/PARTIAL` and no matching `bill_payments`.
- Bills edited after creation (show `BILL_EDIT` history).
Each anomaly row shows bill number, cashier, timestamp, and the offending values.

## 8. UI / UX REQUIREMENTS

### 8.1 POS screen (`pos.html`)
- Cart rows: show per-line discount input, and a **FREE** toggle for free-supply lines.
- Header section: payment method stays; add **split payment** inputs (e.g. cash amount +
  UPI amount auto-computing the balance), and for credit: due-date picker.
- Add charges fields (shipping/packing/round-off) in the totals panel; show live updated
  subtotal, discount, charges, tax, grand total, amount paid, balance.
- Preserve existing interactions (debounced search, qty +/- with stock max, toasts, cart
  badge); reuse the current design tokens.
- Quantity controls must not allow 0/negative (existing behavior), and stock cap logic stays.

### 8.2 Bill history (`bills.html`)
- Add a payment-status column with color badges: PAID / PARTIAL / DUE / REFUNDED.
- Add filter by payment status and date range (client-side or server-side).
- Keep print-A4-report and totals footer.

### 8.3 Bill detail (`bill_detail.html`)
- A5 + thermal layouts: show discounts per line, free-supply labels, charges, round-off,
  amount paid vs grand total, outstanding balance, and due date.
- Payment ledger section listing each `bill_payments` entry (date, amount, method,
  reference, recorded-by).
- Action buttons (RBAC-aware): **Record Payment** (when DUE/PARTIAL), **Refund Lines**,
  **Edit Bill**, plus existing Refund/Cancel.
- Audit history section (from `audit_logs`) showing create/edit/pay/refund events.

## 9. DATA MODEL CHANGES

- `invoices`: add `amount_paid`, `amount_due`, `due_date`, `charges`, `round_off`,
  `discount_total`, `free_supply_total`, `payment_status` (PAID/PARTIAL/DUE/REFUNDED),
  `edit_history` (array), `refunded_lines`.
- New collection `bill_payments`: `{ bill_id, bill_number, amount, method, reference,
  performed_by, created_at }`.
- `audit_logs`: BILL_CREATE details now carry the full snapshot; new action types:
  `BILL_CREATE_REJECTED`, `BILL_PAYMENT`, `BILL_REFUND_LINE`, `BILL_EDIT`.
- `inventory_transactions`: keep `BILL_SALE` / `BILL_REFUND` types; line-refund uses
  `BILL_REFUND` with bill_number in reason.

## 10. TESTING

Extend `tests/` (pytest). Add coverage for at least:
- compute_bill math: discounts, charges, round-off, free lines, GST split (pure unit tests).
- create_bill: split payment, credit DUE, free supply, rejected qty=0 / NaN / negative,
  stock rollback on multi-line failure.
- partial refund: stock restored only for refunded lines; payment ledger integrity.
- record payment: DUE→PARTIAL→PAID transitions.
- reconciliation report: flags each anomaly class.
Run the full suite (`python -m pytest`) — all existing tests must keep passing; update any
that assert the old billing contract.

## 11. CONSTRAINTS & STYLE

- No new dependencies. Keep CSRF + role decorators on every state-changing route.
- Keep responses concise; reuse existing helpers; do not add code comments unless needed.
- Verify with `python -m pytest` after implementation and report the pass/fail summary.

## 12. DELIVERABLES

1. Modified `billing_service.py`, `billing_routes.py`, `pos.html`, `bills.html`,
   `bill_detail.html`, plus new templates/pages for payments, line refund, edit, and the
   reconciliation report.
2. New/changed audit logging in `audit_service.py` call sites.
3. Updated/added tests.
4. A short summary of what was implemented vs. stubbed, and the pytest results.