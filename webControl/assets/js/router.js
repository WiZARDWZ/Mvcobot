/**
 * SPA router for the Mvcobot control panel
 * Handles hash-based navigation and lazy-loads route modules on demand.
 */
import { API_EVENTS } from './api.js';
import { renderToast } from './ui/components.js';

const viewContainer = document.querySelector('[data-router-view]');
const navLinks = Array.from(document.querySelectorAll('[data-route-link]'));
const refreshButton = document.querySelector('[data-action="refresh"]');
const fallbackBanner = document.querySelector('[data-role="fallback-alert"]');

const routes = {
  '#/dashboard': () => import('./ui/dashboard.js'),
  '#/stats': () => import('./ui/stats.js'),
  '#/commands': () => import('./ui/commands.js'),
  '#/blocklist': () => import('./ui/blocklist.js'),
  '#/private-telegram': () => import('./ui/private-telegram.js'),
  '#/settings': () => import('./ui/settings.js'),
  '#/audit-log': () => import('./ui/audit-log.js'),
  '#/dm-bot': () => import('./ui/dm-bot.js'),
};

let activeRouteCleanup = null;
let activeModule = null;

function setActiveNav(hash) {
  navLinks.forEach((link) => {
    if (!hash && link.getAttribute('href') === '#/dashboard') {
      link.classList.add('is-active');
      return;
    }

    const isActive = link.getAttribute('href') === hash;
    link.classList.toggle('is-active', isActive);
  });
}

async function mountRoute(hash, { forceRefresh = false } = {}) {
  const targetHash = hash && routes[hash] ? hash : '#/dashboard';

  if (!forceRefresh && activeModule?.hash === targetHash) {
    await activeModule.instance?.refresh?.();
    return;
  }

  if (activeRouteCleanup) {
    try {
      activeRouteCleanup();
    } catch (error) {
      console.error('Error during route cleanup', error);
    }
    activeRouteCleanup = null;
  }

  viewContainer.innerHTML = '';
  viewContainer.dataset.state = 'loading';

  try {
    const loader = routes[targetHash];
    const module = await loader();
    const result = await module.mount(viewContainer, {
      hash: targetHash,
      onNavigate: (nextHash) => {
        window.location.hash = nextHash;
      },
    });

    activeModule = { hash: targetHash, instance: result };
    activeRouteCleanup = result?.destroy ?? null;
    setActiveNav(targetHash);
    viewContainer.dataset.state = 'ready';
    const mainContent = document.getElementById('main-content');
    if (mainContent) {
      try {
        mainContent.focus({ preventScroll: false });
      } catch (error) {
        mainContent.focus();
      }
    }
  } catch (error) {
    console.error('Failed to mount route', error);
    viewContainer.dataset.state = 'error';
    viewContainer.innerHTML = `<div class="empty-state">خطا در بارگذاری محتوا. ${
      error?.message || ''
    }</div>`;
    renderToast({ message: 'بارگذاری صفحه با خطا مواجه شد.', type: 'error' });
  }
}

function handleHashChange() {
  mountRoute(window.location.hash);
}

window.addEventListener('hashchange', handleHashChange);

refreshButton?.addEventListener('click', () => {
  if (activeModule?.instance?.refresh) {
    activeModule.instance.refresh();
  } else {
    mountRoute(window.location.hash, { forceRefresh: true });
  }
});

let fallbackToastVisible = false;

window.addEventListener(API_EVENTS.FALLBACK, (event) => {
  const message =
    event?.detail?.message || 'اتصال به سرور برقرار نشد؛ داده‌های آزمایشی نمایش داده می‌شوند.';
  if (fallbackBanner) {
    fallbackBanner.textContent = message;
    fallbackBanner.hidden = false;
  }
  if (fallbackToastVisible) return;
  fallbackToastVisible = true;
  renderToast({
    message,
    type: 'warning',
  });
  window.setTimeout(() => {
    fallbackToastVisible = false;
  }, 4000);
});

setActiveNav(window.location.hash);
mountRoute(window.location.hash);
