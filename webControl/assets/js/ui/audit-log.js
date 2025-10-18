/**
 * Audit log tab module.
 */
import { api } from '../api.js';
import {
  createElement,
  createLoadingState,
  createTable,
  formatDateTime,
  formatRelativeTime,
  renderToast,
} from './components.js';

function formatDetails(details) {
  if (!details && details !== 0) {
    return '—';
  }
  if (Array.isArray(details)) {
    return details.join('، ');
  }
  if (typeof details === 'object') {
    return Object.entries(details)
      .map(([key, value]) => `${key}: ${value}`)
      .join(' | ');
  }
  return String(details);
}

export async function mount(container) {
  const heading = createElement('div', { classes: ['section-heading'] });
  const titleWrap = createElement('div');
  titleWrap.append(
    createElement('h3', {
      classes: ['section-heading__title'],
      text: 'گزارش تغییرات سیستم',
    }),
    createElement('p', {
      classes: ['section-heading__subtitle'],
      text: 'آخرین تغییرات اعمال‌شده از طریق کنترل‌پنل در این بخش ثبت می‌شود.',
    })
  );
  heading.appendChild(titleWrap);

  const table = createTable(
    [
      {
        label: 'زمان',
        render: (row) => {
          const wrapper = createElement('div', { classes: ['log-time'] });
          wrapper.append(
            createElement('span', {
              text: formatDateTime(row.timestamp) || '—',
            })
          );
          const relative = formatRelativeTime(row.timestamp);
          if (relative) {
            wrapper.append(
              createElement('span', {
                classes: ['log-time__meta'],
                text: relative,
              })
            );
          }
          return wrapper;
        },
      },
      { label: 'رویداد', field: 'message' },
      {
        label: 'جزئیات',
        render: (row) => formatDetails(row.details),
      },
      {
        label: 'توسط',
        render: (row) => row.actor || 'کنترل‌پنل',
      },
    ],
    { emptyMessage: 'هنوز تغییر ثبت نشده است.' }
  );

  const loadingState = createLoadingState('در حال دریافت گزارش تغییرات...');
  loadingState.hidden = true;

  container.append(heading, table.wrapper, loadingState);

  async function loadAudit(showToast = false) {
    loadingState.hidden = false;
    try {
      const response = await api.getAuditLog();
      const items = response?.items ?? [];
      table.update(items);
      if (showToast) {
        renderToast({ message: 'گزارش تغییرات به‌روزرسانی شد.' });
      }
    } catch (error) {
      console.error('Failed to load audit log', error);
      table.update([]);
      renderToast({ message: 'بارگذاری گزارش تغییرات ناموفق بود.', type: 'error' });
    } finally {
      loadingState.hidden = true;
    }
  }

  await loadAudit();

  return {
    refresh() {
      return loadAudit(true);
    },
    destroy() {
      table.update([]);
    },
  };
}
