/* ============================================================
   Toast Notifications — Auto-dismissing, slide-in from right
   ============================================================ */
const Toast = (() => {
  let container = null;

  function ensureContainer() {
    if (!container) {
      container = document.getElementById('toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
      }
    }
    return container;
  }

  function getIcon(type) {
    const icons = {
      success: 'fa-circle-check',
      danger:  'fa-circle-xmark',
      error:   'fa-circle-xmark',
      warning: 'fa-triangle-exclamation',
      info:    'fa-circle-info',
    };
    return icons[type] || icons.info;
  }

  function show(message, type = 'info', opts = {}) {
    const c = ensureContainer();
    const duration = opts.duration || (type === 'danger' || type === 'error' ? 6000 : 4000);
    const title = opts.title || '';

    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.setAttribute('role', 'alert');
    el.innerHTML = `
      <i class="fa-solid ${getIcon(type)} toast-icon"></i>
      <div class="toast-body">
        ${title ? `<div class="toast-title">${title}</div>` : ''}
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close" aria-label="Close">&times;</button>
      <div class="toast-progress" style="animation-duration: ${duration}ms"></div>
    `;

    const close = () => {
      el.classList.add('toast-exit');
      el.addEventListener('animationend', () => el.remove(), { once: true });
    };

    el.querySelector('.toast-close').addEventListener('click', close);
    c.appendChild(el);

    const timer = setTimeout(close, duration);
    el.addEventListener('mouseenter', () => clearTimeout(timer));
    el.addEventListener('mouseleave', () => setTimeout(close, 1500));

    return el;
  }

  return {
    show,
    success: (msg, opts) => show(msg, 'success', opts),
    error:   (msg, opts) => show(msg, 'error', opts),
    warning: (msg, opts) => show(msg, 'warning', opts),
    info:    (msg, opts) => show(msg, 'info', opts),
  };
})();

/* Convert Flask flash messages to Toast on page load */
document.addEventListener('DOMContentLoaded', () => {
  const flashContainer = document.querySelector('.flash-container');
  if (!flashContainer) return;

  flashContainer.querySelectorAll('.alert').forEach(alert => {
    const text = alert.querySelector('span')?.textContent?.trim() || alert.textContent.trim();
    let type = 'info';
    if (alert.classList.contains('alert-success')) type = 'success';
    else if (alert.classList.contains('alert-danger') || alert.classList.contains('alert-error')) type = 'danger';
    else if (alert.classList.contains('alert-warning')) type = 'warning';
    Toast.show(text, type, { duration: 5000 });
  });

  flashContainer.remove();
});
