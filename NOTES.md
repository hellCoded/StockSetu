# StockSetu UI Logic & Table Pagination Knowledge Base

## User Management Table (`users/list.html`)
- **Bugs → Fix**: Role filter pills previously filtered only the current page in the DOM. Fixed by linking pills directly to server query parameters (`role=...`), preserving database-wide filtering with page reset.
- **Pattern**: Server-side pagination via `components/pagination.html`.
- **Gotchas**: When using in-hero search or filter pills, always submit through GET query parameters or include `role` in the form hidden inputs so pagination links retain the filter context.

## Store Purchases Table (`users/profile.html`)
- **Bugs → Fix**: Fixed hardcoded page size (`8`). Added dynamic page-size selector (`4, 8, 16, 24`) and unified `updatePurchasesPagination` with search filters.
- **Pattern**: Client-side JS pagination for employee purchase sub-table.
- **Gotchas**: Ensure `currentPurchasesPage` resets to 1 whenever search query or page size changes.

## Sales Staff Performance Table (`billing/sales.html`)
- **Bugs → Fix**: Fixed hardcoded staff page size (`12`). Added dynamic page-size selector (`6, 12, 24`) with `setStaffPageSize()`.
- **Pattern**: Client-side JS pagination for sales analytics leaderboard.
- **Gotchas**: Instant search input must reset `currentStaffPage = 1` and recalculate `totalStaffPages` dynamically.

## Products & Inventory Tables (`products/list.html`, `inventory/transactions.html`, `billing/bills.html`)
- **Bugs → Fix**: Verified filter forms omit stale `page` parameter on submission so new searches always land on Page 1.
- **Pattern**: Standard server-side pagination with configurable page size (10, 15, 25, 50, 100).
- **Gotchas**: The reusable component `components/pagination.html` calls `handlePerPageChange()` which automatically resets `page=1`.
