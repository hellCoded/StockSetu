// ============================================================
// Dashboard screen — chart rendering, loading & error states
// Scoped to the .dashboard block only; does not touch other screens.
// ============================================================
(function () {
  'use strict';

  const root = document.querySelector('.dashboard');
  if (!root) return;

  // ── Inline (server-side) data ──
  const dataEl = document.getElementById('dash-chart-data');
  let chartData = {
    stock_by_category: [],
    low_stock_by_category: [],
    top_products_stock: [],
    role_requests_by_status: []
  };
  try {
    if (dataEl) chartData = JSON.parse(dataEl.textContent) || chartData;
  } catch (e) {
    console.error('Dashboard: could not parse chart data.', e);
  }

  const jklcBlue = getComputedStyle(document.documentElement).getPropertyValue('--jklc-blue').trim() || '#0B3D6E';
  const jklcRed = getComputedStyle(document.documentElement).getPropertyValue('--jklc-red').trim() || '#E4132B';

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          font: { family: 'Plus Jakarta Sans', size: 10, weight: '500' },
          boxWidth: 12,
          padding: 8
        }
      }
    }
  };

  const frame = () => new Promise(r => requestAnimationFrame(() => r()));

  function setChartError(container, message) {
    if (container.querySelector('.dash-chart-error')) return;
    const wrap = document.createElement('div');
    wrap.className = 'dash-chart-error';
    wrap.innerHTML =
      '<i class="ri-alert-fill"></i>' +
      '<div>' + message + '</div>' +
      '<button type="button" class="btn btn-sm btn-secondary" data-retry>' +
        '<i class="ri-refresh-line"></i> Retry</button>';
    container.innerHTML = '';
    container.appendChild(wrap);
    wrap.querySelector('[data-retry]').addEventListener('click', () => window.location.reload());
  }

  function setChartEmpty(container, message) {
    container.innerHTML = '<p class="chart-empty">' + message + '</p>';
  }

  // ── 1. Stock by Category (Vertical Bar) ──
  function renderBarChart() {
    const el = document.getElementById('categoryStockChart');
    if (!el) return;
    const container = el.parentElement;
    const rows = chartData.stock_by_category || [];

    if (!rows.length) { setChartEmpty(container, 'No category data available.'); return; }
    if (typeof Chart === 'undefined') { setChartError(container, 'Chart library failed to load.'); return; }

    try {
      new Chart(el.getContext('2d'), {
        type: 'bar',
        data: {
          labels: rows.map(x => x.category),
          datasets: [{
            label: 'Total Stock',
            data: rows.map(x => x.total_stock),
            backgroundColor: jklcBlue,
            hoverBackgroundColor: jklcRed,
            borderRadius: 6,
            borderWidth: 0
          }]
        },
        options: {
          ...commonOptions,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              grid: { display: false },
              ticks: { font: { family: 'Plus Jakarta Sans', size: 9 }, maxRotation: 45, minRotation: 0 }
            },
            y: {
              beginAtZero: true,
              grid: { color: '#f1f5f9' },
              ticks: { font: { family: 'Plus Jakarta Sans', size: 10 } }
            }
          }
        }
      });
    } catch (err) {
      console.error('Dashboard: bar chart failed.', err);
      setChartError(container, 'Unable to render category chart.');
    }
  }

  // ── 2. Role Requests by Status (Donut) ──
  function renderDonutChart() {
    const el = document.getElementById('roleRequestsChart');
    if (!el) return;
    const container = el.parentElement;
    const rows = chartData.role_requests_by_status || [];

    if (!rows.length) { setChartEmpty(container, 'No requests history.'); return; }
    if (typeof Chart === 'undefined') { setChartError(container, 'Chart library failed to load.'); return; }

    try {
      const labels = rows.map(x => String(x.status).toUpperCase());
      const colorMap = {
        PENDING: '#f59e0b',
        APPROVED: '#10b981',
        REJECTED: '#ef4444',
        CANCELLED: '#64748b'
      };
      new Chart(el.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: labels,
          datasets: [{
            data: rows.map(x => x.count),
            backgroundColor: labels.map(l => colorMap[l] || '#94a3b8'),
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: { ...commonOptions, cutout: '65%' }
      });
    } catch (err) {
      console.error('Dashboard: doughnut chart failed.', err);
      setChartError(container, 'Unable to render role requests chart.');
    }
  }

  // ── 3. Top Products by Stock (Horizontal Bar, non-admin) ──
  function renderTopProductsChart() {
    const el = document.getElementById('topProductsChart');
    if (!el) return;
    const container = el.parentElement;
    const rows = chartData.top_products_stock || [];

    if (!rows.length) { setChartEmpty(container, 'No product data available.'); return; }
    if (typeof Chart === 'undefined') { setChartError(container, 'Chart library failed to load.'); return; }

    try {
      new Chart(el.getContext('2d'), {
        type: 'bar',
        data: {
          labels: rows.map(x => x.product_name),
          datasets: [{
            label: 'Stock Quantity',
            data: rows.map(x => x.quantity),
            backgroundColor: jklcBlue,
            hoverBackgroundColor: jklcRed,
            borderRadius: 6,
            borderWidth: 0,
            barThickness: 12
          }]
        },
        options: {
          ...commonOptions,
          indexAxis: 'y',
          plugins: { legend: { display: false } },
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: '#f1f5f9' },
              ticks: { font: { family: 'Plus Jakarta Sans', size: 10 } }
            },
            y: {
              grid: { display: false },
              ticks: { font: { family: 'Plus Jakarta Sans', size: 9 }, autoSkip: false }
            }
          }
        }
      });
    } catch (err) {
      console.error('Dashboard: top products chart failed.', err);
      setChartError(container, 'Unable to render top products chart.');
    }
  }

  // ── 4. Recent Activity Filter Chips ──
  function initActivityFilters() {
    const table = document.getElementById('recent-activity-table');
    if (!table) return;
    const chips = document.querySelectorAll('.activity-chip');
    const rows = [...table.querySelectorAll('tbody tr[data-tx-type]')];
    const emptyRow = table.querySelector('.dash-table-empty');

    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        chips.forEach(c => c.classList.remove('is-active'));
        chip.classList.add('is-active');
        const filter = chip.dataset.filter;
        let visible = 0;
        rows.forEach(row => {
          const match = filter === 'all' || row.dataset.txType === filter;
          row.style.display = match ? '' : 'none';
          if (match) visible++;
        });
        if (emptyRow) emptyRow.style.display = visible === 0 ? '' : 'none';
      });
    });
  }

  // ── Boot: render charts as soon as the skeleton has painted, no artificial delay ──
  async function init() {
    await frame();

    renderBarChart();
    if (document.getElementById('roleRequestsChart')) renderDonutChart();
    renderTopProductsChart();
    initActivityFilters();

    // Fade content in (skeleton/spinner out)
    root.classList.remove('dash-loading');

    // (Re)run KPI counters now that values are visible
    if (typeof window.initKpiCounters === 'function') window.initKpiCounters();
  }

  init();
})();