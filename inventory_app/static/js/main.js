// ============================================================
// Inventory Management System — Interactive UI Layer
// ============================================================

// ── 1. CUSTOM CONFIRM MODAL ─────────────────────────────────
(function buildConfirmModal() {
  const overlay = document.createElement('div');
  overlay.id = 'custom-confirm-overlay';
  overlay.innerHTML = `
    <div id="custom-confirm-box">
      <div id="custom-confirm-icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
      <h4 id="custom-confirm-title">Confirm Action</h4>
      <p id="custom-confirm-message"></p>
      <div class="custom-confirm-actions">
        <button id="custom-confirm-cancel" class="btn btn-secondary"><i class="fa-solid fa-xmark"></i> Cancel</button>
        <button id="custom-confirm-ok" class="btn btn-danger"><i class="fa-solid fa-check"></i> Confirm</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) _resolveConfirm(false); });
  document.getElementById('custom-confirm-cancel').addEventListener('click', () => _resolveConfirm(false));
  document.getElementById('custom-confirm-ok').addEventListener('click', () => _resolveConfirm(true));
})();

let _confirmResolve = null;
function _resolveConfirm(result) {
  document.getElementById('custom-confirm-overlay').classList.remove('active');
  if (_confirmResolve) { _confirmResolve(result); _confirmResolve = null; }
}
function showConfirm(message, title = 'Confirm Action') {
  return new Promise((resolve) => {
    _confirmResolve = resolve;
    document.getElementById('custom-confirm-message').textContent = message;
    document.getElementById('custom-confirm-title').textContent = title;
    document.getElementById('custom-confirm-overlay').classList.add('active');
  });
}

// ── 2. TOAST NOTIFICATION SYSTEM ────────────────────────────
(function buildToastContainer() {
  const c = document.createElement('div');
  c.id = 'toast-container';
  document.body.appendChild(c);
})();

const TOAST_ICONS = {
  success: 'fa-circle-check', error: 'fa-circle-xmark', danger: 'fa-circle-xmark',
  warning: 'fa-triangle-exclamation', info: 'fa-circle-info', message: 'fa-circle-info',
};

function showToast(message, category = 'info', duration = 5500) {
  const container = document.getElementById('toast-container');
  const icon = TOAST_ICONS[category] || 'fa-circle-info';
  const cat = category === 'danger' ? 'error' : category;
  const toast = document.createElement('div');
  toast.className = `toast toast-${cat}`;
  toast.innerHTML = `
    <div class="toast-icon"><i class="fa-solid ${icon}"></i></div>
    <div class="toast-body">
      <div class="toast-message">${message}</div>
      <div class="toast-progress"><div class="toast-progress-bar"></div></div>
    </div>
    <button class="toast-close" title="Dismiss"><i class="fa-solid fa-xmark"></i></button>
  `;
  container.appendChild(toast);
  requestAnimationFrame(() => { requestAnimationFrame(() => toast.classList.add('toast-visible')); });
  const bar = toast.querySelector('.toast-progress-bar');
  setTimeout(() => { bar.style.transition = `width ${duration}ms linear`; bar.style.width = '0%'; }, 50);
  const dismiss = () => {
    toast.classList.remove('toast-visible');
    setTimeout(() => toast.remove(), 400);
  };
  toast.querySelector('.toast-close').addEventListener('click', dismiss);
  setTimeout(dismiss, duration);
}

function initFlashToasts() {
  document.querySelectorAll('.flash-container .alert').forEach(alert => {
    const msg = alert.querySelector('span')?.textContent?.trim() || '';
    const cls = [...alert.classList].find(c => c.startsWith('alert-'))?.replace('alert-', '') || 'info';
    if (msg) showToast(msg, cls);
    alert.remove();
  });
}

// ── 3. KPI COUNTER ANIMATION ─────────────────────────────────
function animateCounter(el, target, duration, prefix, suffix) {
  const isFloat = !Number.isInteger(target);
  const decimals = isFloat ? 2 : 0;
  let start = null;
  function step(ts) {
    if (!start) start = ts;
    const p = Math.min((ts - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    const cur = target * eased;
    el.textContent = prefix + cur.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
    if (p < 1) requestAnimationFrame(step);
    else el.textContent = prefix + target.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
  }
  requestAnimationFrame(step);
}function initKpiCounters() {
  document.querySelectorAll('[data-counter]').forEach(el => {
    const raw = parseFloat(el.dataset.counter);
    const prefix = el.dataset.counterPrefix || '';
    const suffix = el.dataset.counterSuffix || '';
    if (!isNaN(raw)) animateCounter(el, raw, 1400, prefix, suffix);
  });
}

function initInstantSearch() {
  document.querySelectorAll('.instant-search-input').forEach(input => {
    const table = document.getElementById(input.dataset.table || 'product-table');
    if (!table) return;
    const rows = [...table.querySelectorAll('tbody tr:not(.empty-row)')];
    const emptyRow = table.querySelector('.empty-row');
    const grid = document.querySelector('.product-view-grid');
    const cards = grid ? [...grid.querySelectorAll('.product-card')] : [];
    const gridEmpty = grid ? grid.querySelector('.empty-table') : null;
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach(row => {
        const match = !q || row.textContent.toLowerCase().includes(q);
        row.style.display = match ? '' : 'none';
        if (match) visible++;
      });
      if (emptyRow) emptyRow.style.display = visible === 0 ? '' : 'none';
      let gridVisible = 0;
      cards.forEach(card => {
        const match = !q || card.textContent.toLowerCase().includes(q);
        card.style.display = match ? '' : 'none';
        if (match) gridVisible++;
      });
      if (gridEmpty) gridEmpty.style.display = gridVisible === 0 ? '' : 'none';
    });
  });
}

// ── 5b. PRODUCT VIEW TOGGLE (List / Card grid) ──────────────
function initProductViewToggle() {
  const toggle = document.querySelector('.view-toggle');
  if (!toggle) return;
  const listView = document.querySelector('.product-view-list');
  const gridView = document.querySelector('.product-view-grid');
  if (!listView || !gridView) return;

  const saved = localStorage.getItem('products-view') || 'list';
  const apply = (mode) => {
    listView.hidden = mode !== 'list';
    gridView.hidden = mode !== 'grid';
    toggle.querySelectorAll('.view-toggle-btn').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.view === mode);
    });
    localStorage.setItem('products-view', mode);
  };
  apply(saved);

  toggle.querySelectorAll('.view-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => apply(btn.dataset.view));
  });
}

function initSortableTable() {
  document.querySelectorAll('.data-table.sortable thead th[data-sort]').forEach(th => {
    th.style.cursor = 'pointer';
    th.style.userSelect = 'none';
    const ind = document.createElement('span');
    ind.className = 'sort-indicator';
    ind.innerHTML = ' <i class="fa-solid fa-sort" style="opacity:0.3;font-size:0.72em;"></i>';
    th.appendChild(ind);
    th.addEventListener('click', () => {
      const tbody = th.closest('table').querySelector('tbody');
      const col = th.cellIndex;
      const asc = th.dataset.sortDir !== 'asc';
      th.dataset.sortDir = asc ? 'asc' : 'desc';
      th.closest('thead').querySelectorAll('th[data-sort]').forEach(o => {
        if (o !== th) { o.dataset.sortDir = ''; const i = o.querySelector('.sort-indicator i'); if (i) { i.className = 'fa-solid fa-sort'; i.style.opacity = '0.3'; } }
      });
      const i = ind.querySelector('i');
      i.className = asc ? 'fa-solid fa-sort-up' : 'fa-solid fa-sort-down';
      i.style.opacity = '1';
      const rows = [...tbody.querySelectorAll('tr:not(.empty-row)')];
      rows.sort((a, b) => {
        const av = a.cells[col]?.textContent?.trim() || '';
        const bv = b.cells[col]?.textContent?.trim() || '';
        const an = parseFloat(av.replace(/[^0-9.-]/g, ''));
        const bn = parseFloat(bv.replace(/[^0-9.-]/g, ''));
        if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

// ── 6. LIVE STOCK PREVIEW WIDGET ─────────────────────────────
function initStockPreview() {
  const productSelect = document.getElementById('product_name');
  const quantityInput = document.getElementById('quantity') || document.getElementById('target_quantity');
  const previewBox    = document.getElementById('stock-preview');
  const stockDataEl   = document.getElementById('stock-data-json');
  if (!productSelect || !previewBox || !stockDataEl) return;

  let stockMap = {};
  try { stockMap = JSON.parse(stockDataEl.textContent); } catch(e) {}
  const isAdjust  = !!document.getElementById('target_quantity');
  const isStockOut = document.body.dataset.stockMode === 'out';

  function updatePreview() {
    const name = productSelect.value;
    const qty  = parseFloat(quantityInput?.value) || 0;
    const info = stockMap[name];
    if (!info || !name) { previewBox.style.display = 'none'; return; }
    const current = info.quantity;
    let projected = isAdjust ? (qty >= 0 ? qty : current) : (isStockOut ? current - qty : current + qty);
    const diff = projected - current;
    const diffSign = diff >= 0 ? '+' : '';
    const safeProjected = Math.max(projected, 0);
    const color = projected < 0 ? '#dc2626' : (diff < 0 ? '#f59e0b' : '#10b981');
    const icon  = projected < 0 ? 'fa-circle-xmark' : (diff < 0 ? 'fa-arrow-trend-down' : 'fa-arrow-trend-up');
    const decimals = info.isFloat ? 2 : 0;
    previewBox.style.display = 'flex';
    previewBox.innerHTML = `
      <div class="stock-preview-icon" style="color:${color};"><i class="fa-solid ${icon}"></i></div>
      <div class="stock-preview-body">
        <div class="stock-preview-label">Stock Preview — <strong>${name}</strong></div>
        <div class="stock-preview-row">
          <span><i class="fa-solid fa-database"></i> Current: <strong>${Number(current).toFixed(decimals)} ${info.unit}</strong></span>
          <span class="stock-arrow"><i class="fa-solid fa-arrow-right"></i></span>
          <span style="color:${color};font-weight:600;">${safeProjected.toFixed(decimals)} ${info.unit} <em style="font-weight:400;font-size:0.82em;">(${diffSign}${diff.toFixed(decimals)})</em></span>
        </div>
        ${projected < 0 ? '<div class="stock-preview-warn"><i class="fa-solid fa-triangle-exclamation"></i> Quantity exceeds available stock!</div>' : ''}
        ${info.minimum_stock > 0 && safeProjected <= info.minimum_stock && diff !== 0
          ? `<div class="stock-preview-warn warn-yellow"><i class="fa-solid fa-bell"></i> Result will be at or below minimum stock threshold (${info.minimum_stock} ${info.unit})</div>` : ''}
      </div>`;
  }

  productSelect.addEventListener('change', updatePreview);
  if (quantityInput) quantityInput.addEventListener('input', updatePreview);
  updatePreview();
}

// ── 7. FORM SUBMIT LOADING STATE ─────────────────────────────
function initFormLoadingState() {
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function() {
      const btn = form.querySelector('button[type="submit"]');
      if (!btn || btn.dataset.loading) return;
      btn.dataset.loading = '1';
      btn.style.pointerEvents = 'none';
      btn.style.opacity = '0.75';
      const orig = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing\u2026';

      // Show page-level overlay for heavy forms (file uploads, bulk ops)
      if (form.enctype === 'multipart/form-data' || form.querySelector('[data-heavy]')) {
        showPageLoading('Processing your request\u2026', 'This may take a few seconds');
      }

      // Persist until page unloads (no timeout revert)
      window.addEventListener('beforeunload', () => {
        btn.innerHTML = orig;
        btn.style.pointerEvents = 'auto';
        btn.style.opacity = '1';
        delete btn.dataset.loading;
      });
    });
  });
}

// ── 7b. PAGE-LEVEL LOADING OVERLAY ───────────────────────────
function showPageLoading(title, subtitle) {
  let overlay = document.getElementById('page-loading-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'page-loading-overlay';
    overlay.className = 'page-loading-overlay';
    overlay.innerHTML = `
      <div class="page-spinner">
        <i class="fa-solid fa-spinner fa-spin"></i>
        <strong></strong>
        <span></span>
      </div>`;
    document.body.appendChild(overlay);
  }
  overlay.querySelector('strong').textContent = title || 'Loading\u2026';
  overlay.querySelector('span').textContent = subtitle || '';
  requestAnimationFrame(() => overlay.classList.add('active'));
}

function hidePageLoading() {
  const overlay = document.getElementById('page-loading-overlay');
  if (overlay) {
    overlay.classList.remove('active');
    setTimeout(() => overlay.remove(), 300);
  }
}

// Show loading overlay for any internal navigation link
function initNavigationLoading() {
  document.addEventListener('click', function(e) {
    const link = e.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href');
    // Skip external, anchor-only, javascript:, downloads
    if (!href || href.startsWith('#') || href.startsWith('javascript:') ||
        href.startsWith('http') || href.endsWith('.pdf') || href.endsWith('.xlsx') ||
        link.hasAttribute('download') || link.target === '_blank') return;
    // Skip if modifier key held (new tab)
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    // Skip if link is inside a form
    if (link.closest('form')) return;
    showPageLoading('Loading\u2026');
  });

  // Hide overlay when page finishes loading (covers back/forward too)
  window.addEventListener('pageshow', hidePageLoading);
}

// ── 8. data-confirm → custom modal ───────────────────────────
function initCustomConfirmTriggers() {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    const msg = el.getAttribute('data-confirm');
    el.removeAttribute('data-confirm');
    el.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const ok = await showConfirm(msg || 'Are you sure?');
      if (ok) {
        const parentForm = el.closest('form');
        if (parentForm) {
          parentForm.submit();
        } else if (el.href) {
          window.location.href = el.href;
        }
      }
    });
  });
}

// ── 9. TABLE ROW CLICK NAVIGATION ────────────────────────────
function initRowNavigation() {
  document.querySelectorAll('.data-table.clickable-rows tbody tr').forEach(row => {
    const link = row.querySelector('a');
    if (!link) return;
    row.style.cursor = 'pointer';
    row.addEventListener('click', (e) => {
      if (e.target.tagName === 'BUTTON' || e.target.tagName === 'SELECT' ||
          e.target.tagName === 'INPUT' || e.target.closest('form') || e.target.tagName === 'A') return;
      link.click();
    });
  });
}

// ── 10. NAVBAR ALERT BELL TOGGLE ─────────────────────────────
function initAlertBell() {
  const bell = document.getElementById('alert-bell');
  const wrap = bell ? bell.closest('.alert-bell-wrap') : null;
  if (!bell || !wrap) return;

  bell.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = wrap.classList.toggle('open');
    bell.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  document.addEventListener('click', (e) => {
    if (!wrap.contains(e.target)) {
      wrap.classList.remove('open');
      bell.setAttribute('aria-expanded', 'false');
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      wrap.classList.remove('open');
      bell.setAttribute('aria-expanded', 'false');
    }
  });
}

// ── INIT ALL ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('mobile-sidebar-toggle');
  const sidebar   = document.querySelector('.sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      sidebar.classList.toggle('mobile-open');
    });
    
    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
      if (sidebar.classList.contains('mobile-open')) {
        if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
          sidebar.classList.remove('mobile-open');
        }
      }
    });
  }

  initFlashToasts();
  initKpiCounters();
  initInstantSearch();
  initSortableTable();
  initProductViewToggle();
  initStockPreview();
  initFormLoadingState();
  initNavigationLoading();
  initCustomConfirmTriggers();
  initRowNavigation();
  initAlertBell();
});

// ── Global helpers ────────────────────────────────────────────
function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const icon = btn.querySelector('i');
  if (input.type === 'password') {
    input.type = 'text';
    icon?.classList.replace('fa-eye', 'fa-eye-slash');
  } else {
    input.type = 'password';
    icon?.classList.replace('fa-eye-slash', 'fa-eye');
  }
}
