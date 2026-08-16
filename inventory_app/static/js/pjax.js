// ============================================================
// PJAX-style Client-Side Navigation
// Intercepts sidebar/content link clicks, fetches via AJAX,
// and replaces only the content area — no full page reload.
// ============================================================
(function() {
  'use strict';

  const CONTENT_SELECTOR = '#main-content';
  const SIDEBAR_SELECTOR = '.sidebar';
  const NAVBAR_BREADCRUMB = '.top-navbar h2 + div p';
  const TRANSITION_MS = 150;

  // Routes that should ALWAYS do a full reload (forms, exports, auth)
  const FULL_RELOAD_PATTERNS = [
    /\/logout/,
    /\/login/,
    /\/register/,
    /\/export\//,
    /\.pdf$/,
    /\.xlsx$/,
    /\/bulk-stock-in\/confirm/
  ];

  // Links that arePJAX-eligible (same-origin, GET, content area)
  function isPJAXEligible(link) {
    if (!link || !link.href) return false;
    if (link.hasAttribute('data-no-pjax')) return false;
    if (link.target === '_blank') return false;
    if (link.protocol !== location.protocol || link.hostname !== location.hostname) return false;
    if (FULL_RELOAD_PATTERNS.test(link.pathname)) return false;
    // Don't intercept POST forms
    if (link.closest('form[data-method="post"]')) return false;
    return true;
  }

  let isNavigating = false;
  let contentEl = null;

  function getContentEl() {
    if (!contentEl) contentEl = document.querySelector(CONTENT_SELECTOR);
    return contentEl;
  }

  // Show a subtle loading bar at the top
  function showLoadingBar() {
    let bar = document.getElementById('pjax-loading-bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'pjax-loading-bar';
      bar.style.cssText = 'position:fixed;top:0;left:0;height:3px;background:var(--color-primary,#0b3d6e);z-index:99999;transition:width 0.3s ease;width:0%;';
      document.body.appendChild(bar);
    }
    requestAnimationFrame(() => { bar.style.width = '60%'; });
    return bar;
  }

  function hideLoadingBar(bar) {
    if (!bar) return;
    bar.style.width = '100%';
    setTimeout(() => { bar.style.opacity = '0'; setTimeout(() => bar.remove(), 300); }, 200);
  }

  // Update sidebar active link
  function updateSidebarActive(pathname) {
    const sidebar = document.querySelector(SIDEBAR_SELECTOR);
    if (!sidebar) return;
    sidebar.querySelectorAll('.sidebar-link').forEach(link => {
      const href = link.getAttribute('href');
      if (!href) return;
      const url = new URL(href, location.origin);
      const isActive = pathname === url.pathname || 
                       (url.pathname !== '/' && pathname.startsWith(url.pathname));
      link.classList.toggle('active', isActive);
    });
  }

  // Update navbar breadcrumb text
  function updateBreadcrumb(endpoint) {
    const el = document.querySelector('.top-navbar p, .top-navbar div[style*="font-size: 0.72rem"]');
    if (!el || !endpoint) return;
    const map = {
      'dashboard.index': 'Overview',
      'products': 'Products',
      'inventory': 'Inventory',
      'billing': 'Billing',
      'users': 'Users'
    };
    for (const [key, label] of Object.entries(map)) {
      if (endpoint.startsWith(key) || endpoint === key) {
        el.textContent = label;
        return;
      }
    }
    el.textContent = endpoint.replace(/_/g, ' ').replace('.', ' › ').replace(/\b\w/g, c => c.toUpperCase());
  }

  // Navigate via fetch
  async function navigate(url, pushState) {
    if (isNavigating) return;
    isNavigating = true;

    const bar = showLoadingBar();
    const content = getContentEl();

    try {
      const resp = await fetch(url, {
        headers: { 'X-PJAX': '1', 'X-Requested-With': 'XMLHttpRequest' }
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const html = await resp.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');

      // Extract new content
      const newContent = doc.querySelector(CONTENT_SELECTOR);
      if (!newContent) throw new Error('Content block not found');

      // Extract new title
      const newTitle = doc.querySelector('title');
      if (newTitle) document.title = newTitle.textContent;

      // Extract endpoint from body or meta
      const newEndpoint = doc.querySelector('meta[name="pjx-endpoint"]')?.content;

      // Fade out old content
      content.style.opacity = '0';
      content.style.transform = 'translateY(8px)';

      await new Promise(r => setTimeout(r, TRANSITION_MS));

      // Replace content
      content.innerHTML = newContent.innerHTML;

      // Transfer data attributes
      for (const attr of newContent.attributes) {
        content.setAttribute(attr.name, attr.value);
      }

      // Fade in new content
      requestAnimationFrame(() => {
        content.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        content.style.opacity = '1';
        content.style.transform = 'translateY(0)';
      });

      // Update sidebar
      const urlObj = new URL(url, location.origin);
      updateSidebarActive(urlObj.pathname);

      // Update breadcrumb
      if (newEndpoint) updateBreadcrumb(newEndpoint);

      // Push browser history
      if (pushState !== false) {
        history.pushState({ pjax: true }, '', url);
      }

      // Re-initialize JS modules needed for the new page
      reinitPageScripts();

      // Scroll to top
      window.scrollTo({ top: 0, behavior: 'instant' });

    } catch (err) {
      // Fallback: full reload
      console.warn('[PJAX] Fallback to full reload:', err.message);
      window.location.href = url;
    } finally {
      hideLoadingBar(bar);
      isNavigating = false;
    }
  }

  // Re-initialize page-specific JS after content swap
  function reinitPageScripts() {
    // Re-run DOMContentLoaded-dependent initializers
    if (typeof initFlashToasts === 'function') initFlashToasts();
    if (typeof initKpiCounters === 'function') initKpiCounters();
    if (typeof initInstantSearch === 'function') initInstantSearch();
    if (typeof initSortableTable === 'function') initSortableTable();
    if (typeof initProductViewToggle === 'function') initProductViewToggle();
    if (typeof initStockPreview === 'function') initStockPreview();
    if (typeof initFormLoadingState === 'function') initFormLoadingState();
    if (typeof initCustomConfirmTriggers === 'function') initCustomConfirmTriggers();
    if (typeof initRowNavigation === 'function') initRowNavigation();
    if (typeof initAlertBell === 'function') initAlertBell();
    if (typeof initFilterActiveState === 'function') initFilterActiveState();
    if (typeof initScrollReveal === 'function') initScrollReveal();
    if (typeof initNavbarScroll === 'function') initNavbarScroll();

    // Re-bind inline scripts that may exist in the new content
    const scripts = document.querySelectorAll(CONTENT_SELECTOR + ' script');
    scripts.forEach(old => {
      const s = document.createElement('script');
      s.textContent = old.textContent;
      document.body.appendChild(s);
      s.remove();
    });

    // Re-init dark mode toggle if needed
    const saved = localStorage.getItem('theme') || 'light';
    if (saved === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
  }

  // Event delegation for link clicks
  document.addEventListener('click', function(e) {
    const link = e.target.closest('a');
    if (!link || !isPJAXEligible(link)) return;

    // Don't intercept sidebar-brand links (logo should full reload)
    if (link.closest('.sidebar-brand')) return;

    // Don't intercept if modifier keys held
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

    // Only intercept links within app container
    if (!link.closest('.app-container') && !link.closest('.main-wrapper') && !link.closest('.sidebar')) return;

    e.preventDefault();
    navigate(link.href, true);
  }, false);

  // Handle browser back/forward
  window.addEventListener('popstate', function(e) {
    if (e.state && e.state.pjax) {
      navigate(location.href, false);
    }
  });

  // Expose for manual use
  window.__pjax = { navigate };

})();
