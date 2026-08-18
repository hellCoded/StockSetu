// app-base.js – Extracted from base.html inline <script>
// Loaded with defer, so DOM is ready.

(function() {
  // Dark mode toggle
  var saved = localStorage.getItem('theme') || 'light';
  if (saved === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
  document.addEventListener('DOMContentLoaded', function() {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', function() {
      var current = document.documentElement.getAttribute('data-theme');
      var next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      var icon = btn.querySelector('i');
      if (icon) icon.className = next === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
    });
    var icon = btn.querySelector('i');
    if (icon) icon.className = saved === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';

    // Mobile sidebar toggle
    var sidebar = document.querySelector('.sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    var toggle = document.getElementById('mobile-sidebar-toggle');
    if (toggle && sidebar) {
      toggle.addEventListener('click', function() {
        sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('show');
      });
    }
    if (overlay) {
      overlay.addEventListener('click', function() {
        if (sidebar) sidebar.classList.remove('open');
        overlay.classList.remove('show');
      });
    }

    // ── Modern Hovering & Pinned Sidebar System (Desktop) ──
    var mqDesktop = window.matchMedia('(min-width: 769px)');
    var body = document.body;
    var hoverTimer = null;

    function getSidebarMode() {
      try {
        return localStorage.getItem('sidebar-mode') || 'hover';
      } catch(e) {
        return 'hover';
      }
    }

    function applySidebarMode(mode) {
      if (mode === 'hover') {
        body.classList.add('sidebar-hover-mode');
      } else {
        body.classList.remove('sidebar-hover-mode', 'sidebar-hover-active');
      }
      try { localStorage.setItem('sidebar-mode', mode); } catch(e) {}
      updateToggleBtn(mode);
    }

    function updateToggleBtn(mode) {
      var deskToggle = document.getElementById('desk-sidebar-toggle');
      if (deskToggle) {
        if (mode === 'hover') {
          deskToggle.setAttribute('title', 'Pin Sidebar (Ctrl+S)');
          deskToggle.classList.remove('active');
        } else {
          deskToggle.setAttribute('title', 'Unpin Sidebar to Hover Mode (Ctrl+S)');
          deskToggle.classList.add('active');
        }
      }
    }

    function showHoverSidebar() {
      if (!body.classList.contains('sidebar-hover-mode')) return;
      clearTimeout(hoverTimer);
      if (!body.classList.contains('sidebar-hover-active')) {
        body.classList.add('sidebar-hover-active');
      }
    }

    function hideHoverSidebarWithDelay(delayMs) {
      if (!body.classList.contains('sidebar-hover-mode')) return;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(function() {
        body.classList.remove('sidebar-hover-active');
      }, delayMs !== undefined ? delayMs : 60);
    }

    if (mqDesktop.matches && sidebar) {
      var initialMode = getSidebarMode();
      applySidebarMode(initialMode);

      // Edge and tab hover triggers smooth floating slide-in
      document.addEventListener('mousemove', function(e) {
        if (body.classList.contains('sidebar-hover-mode')) {
          if (e.clientX <= 24) {
            showHoverSidebar();
          } else if (e.clientX > 250 && body.classList.contains('sidebar-hover-active')) {
            hideHoverSidebarWithDelay(60);
          }
        }
      });

      sidebar.addEventListener('mouseenter', function() {
        if (body.classList.contains('sidebar-hover-mode')) {
          showHoverSidebar();
        }
      });

      sidebar.addEventListener('mouseleave', function() {
        if (body.classList.contains('sidebar-hover-mode')) {
          hideHoverSidebarWithDelay(60);
        }
      });

      var hoverZone = document.getElementById('sidebar-hover-zone');
      if (hoverZone) {
        hoverZone.addEventListener('mouseenter', showHoverSidebar);
      }

      var revealTab = document.getElementById('sidebar-reveal-tab');
      if (revealTab) {
        revealTab.addEventListener('mouseenter', showHoverSidebar);
        revealTab.addEventListener('click', function() {
          applySidebarMode('pinned');
        });
      }

      var pinToggle = document.getElementById('sidebar-pin-toggle');
      if (pinToggle) {
        pinToggle.addEventListener('click', function(e) {
          e.stopPropagation();
          var current = body.classList.contains('sidebar-hover-mode') ? 'hover' : 'pinned';
          applySidebarMode(current === 'hover' ? 'pinned' : 'hover');
        });
      }

      var deskToggle = document.getElementById('desk-sidebar-toggle');
      if (deskToggle) {
        deskToggle.addEventListener('click', function() {
          var current = body.classList.contains('sidebar-hover-mode') ? 'hover' : 'pinned';
          applySidebarMode(current === 'hover' ? 'pinned' : 'hover');
        });
      }

      document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && !e.shiftKey && !e.altKey) {
          e.preventDefault();
          var current = body.classList.contains('sidebar-hover-mode') ? 'hover' : 'pinned';
          applySidebarMode(current === 'hover' ? 'pinned' : 'hover');
        }
      });
    }

    // Sortable table columns
    document.querySelectorAll('th.sortable').forEach(function(th) {
      th.addEventListener('click', function() {
        var table = th.closest('table');
        var tbody = table.querySelector('tbody');
        var idx = Array.from(th.parentNode.children).indexOf(th);
        var rows = Array.from(tbody.querySelectorAll('tr'));
        var isAsc = th.classList.contains('sort-asc');

        table.querySelectorAll('th.sortable').forEach(function(h) {
          h.classList.remove('sort-asc', 'sort-desc');
        });

        rows.sort(function(a, b) {
          var aVal = a.children[idx] ? a.children[idx].textContent.trim() : '';
          var bVal = b.children[idx] ? b.children[idx].textContent.trim() : '';
          var aNum = parseFloat(aVal.replace(/[₹,]/g, ''));
          var bNum = parseFloat(bVal.replace(/[₹,]/g, ''));
          if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAsc ? bNum - aNum : aNum - bNum;
          }
          return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
        });

        th.classList.add(isAsc ? 'sort-desc' : 'sort-asc');
        rows.forEach(function(r) { tbody.appendChild(r); });
      });
    });

    // Bulk select
    var selectAll = document.getElementById('select-all');
    var bulkCheckboxes = document.querySelectorAll('.bulk-checkbox');
    var bulkBar = document.getElementById('bulk-actions');
    var bulkCount = document.getElementById('bulk-count');

    if (selectAll) {
      selectAll.addEventListener('change', function() {
        bulkCheckboxes.forEach(function(cb) { cb.checked = selectAll.checked; });
        updateBulkBar();
      });
    }
    bulkCheckboxes.forEach(function(cb) {
      cb.addEventListener('change', updateBulkBar);
    });

    function updateBulkBar() {
      var checked = document.querySelectorAll('.bulk-checkbox:checked').length;
      if (bulkBar) bulkBar.classList.toggle('show', checked > 0);
      if (bulkCount) bulkCount.textContent = checked + ' selected';
      if (selectAll) selectAll.checked = checked === bulkCheckboxes.length && checked > 0;
    }

    // Auto-save form drafts to localStorage
    var saveTimer = null;
    var indicator = document.createElement('div');
    indicator.className = 'autosave-indicator';
    indicator.innerHTML = '<span class="dot"></span> Draft saved';
    document.body.appendChild(indicator);

    document.querySelectorAll('form[data-autosave]').forEach(function(form) {
      var key = 'draft_' + (form.dataset.autosave || form.action);
      // Restore saved values
      try {
        var savedDraft = JSON.parse(localStorage.getItem(key));
        if (savedDraft) {
          Object.keys(savedDraft).forEach(function(name) {
            var el = form.querySelector('[name="' + name + '"]');
            if (el && !el.value) el.value = savedDraft[name];
          });
        }
      } catch(e) {}

      form.addEventListener('input', function() {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(function() {
          var data = {};
          form.querySelectorAll('input, textarea, select').forEach(function(el) {
            if (el.name) data[el.name] = el.value;
          });
          localStorage.setItem(key, JSON.stringify(data));
          indicator.classList.add('show');
          setTimeout(function() { indicator.classList.remove('show'); }, 2000);
        }, 1000);
      });

      form.addEventListener('submit', function() {
        localStorage.removeItem(key);
      });
    });

    // Inline validation
    document.querySelectorAll('form[data-validate]').forEach(function(form) {
      form.querySelectorAll('[required]').forEach(function(el) {
        el.addEventListener('blur', function() {
          el.classList.toggle('is-invalid', !el.value.trim());
          el.classList.toggle('is-valid', !!el.value.trim());
        });
      });
      form.addEventListener('submit', function(e) {
        var invalid = false;
        form.querySelectorAll('[required]').forEach(function(el) {
          if (!el.value.trim()) {
            el.classList.add('is-invalid');
            invalid = true;
          }
        });
        if (invalid) e.preventDefault();
      });
    });
  });
})();
