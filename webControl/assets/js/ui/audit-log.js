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

  const pagination = createElement('div', { classes: ['pagination'] });
  const prevButton = createElement('button', {
    classes: ['pagination__button'],
    attrs: { type: 'button' },
    text: 'قبلی',
  });
  const nextButton = createElement('button', {
    classes: ['pagination__button'],
    attrs: { type: 'button' },
    text: 'بعدی',
  });
  const pageInfo = createElement('span', { classes: ['pagination__info'], text: '' });
  pagination.append(prevButton, pageInfo, nextButton);

  container.append(heading, table.wrapper, pagination, loadingState);

  let currentPage = 1;
  const pageSize = 20;
  let totalPages = 1;
  let totalItems = 0;
  let isLoading = false;

  function updatePagination() {
    const infoText = `صفحه ${currentPage} از ${totalPages}`;
    pageInfo.textContent = infoText;
    prevButton.disabled = isLoading || currentPage <= 1;
    nextButton.disabled = isLoading || currentPage >= totalPages;
    pagination.hidden = totalItems <= pageSize;
  }

  async function loadAudit({ page = currentPage, toast = false } = {}) {
    isLoading = true;
    loadingState.hidden = false;
    updatePagination();
    try {
      const response = await api.getAuditLog({ page, pageSize });
      const items = response?.items ?? [];
      currentPage = response?.page ?? page;
      totalItems = response?.total ?? items.length;
      totalPages = response?.pages ?? Math.max(1, Math.ceil(totalItems / pageSize));
      table.update(items);
      if (toast) {
        renderToast({ message: 'گزارش تغییرات به‌روزرسانی شد.' });
      }
    } catch (error) {
      console.error('Failed to load audit log', error);
      table.update([]);
      totalItems = 0;
      totalPages = 1;
      renderToast({ message: 'بارگذاری گزارش تغییرات ناموفق بود.', type: 'error' });
    } finally {
      isLoading = false;
      loadingState.hidden = true;
      updatePagination();
    }
  }

  function handlePrevClick() {
    if (currentPage > 1 && !isLoading) {
      loadAudit({ page: currentPage - 1 });
    }
  }

  function handleNextClick() {
    if (currentPage < totalPages && !isLoading) {
      loadAudit({ page: currentPage + 1 });
    }
  }

  prevButton.addEventListener('click', handlePrevClick);
  nextButton.addEventListener('click', handleNextClick);

  await loadAudit();

  return {
    refresh() {
      return loadAudit({ page: currentPage, toast: true });
    },
    destroy() {
      table.update([]);
      prevButton.removeEventListener('click', handlePrevClick);
      nextButton.removeEventListener('click', handleNextClick);
    },
  };
}
