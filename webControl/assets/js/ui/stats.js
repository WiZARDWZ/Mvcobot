import { api } from '../api.js';
import {
  createElement,
  createLoadingState,
  createTable,
  renderToast,
} from './components.js';

const RANGE_OPTIONS = [
  { value: '1m', label: 'یک ماه اخیر' },
  { value: '2m', label: 'دو ماه اخیر' },
  { value: '3m', label: 'سه ماه اخیر' },
  { value: '6m', label: 'شش ماه اخیر' },
  { value: '1y', label: 'یک سال اخیر' },
  { value: 'all', label: 'کل' },
];

const SORT_OPTIONS = [
  { value: 'desc', label: 'بیشترین درخواست' },
  { value: 'asc', label: 'کمترین درخواست' },
];

export async function mount(container) {
  const heading = createElement('div', { classes: ['section-heading'] });
  heading.append(
    createElement('h3', { classes: ['section-heading__title'], text: 'آمار درخواست کدها' }),
    createElement('p', {
      classes: ['section-heading__subtitle'],
      text: 'گزارش تجمیعی کدهای استعلام‌شده در پلتفرم‌ها به تفکیک تعداد درخواست.',
    })
  );

  const filterBar = createElement('div', { classes: ['filter-bar'] });
  const rangeWrapper = createElement('label', {
    classes: ['filter-bar__group'],
    text: 'بازه زمانی',
  });
  const rangeSelect = createElement('select', { classes: ['filter-bar__select'] });
  RANGE_OPTIONS.forEach((option) => {
    const opt = createElement('option', { text: option.label, attrs: { value: option.value } });
    rangeSelect.appendChild(opt);
  });
  rangeWrapper.appendChild(rangeSelect);

  const sortWrapper = createElement('label', {
    classes: ['filter-bar__group'],
    text: 'مرتب‌سازی',
  });
  const sortSelect = createElement('select', { classes: ['filter-bar__select'] });
  SORT_OPTIONS.forEach((option) => {
    const opt = createElement('option', { text: option.label, attrs: { value: option.value } });
    sortSelect.appendChild(opt);
  });
  sortWrapper.appendChild(sortSelect);

  const applyButton = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'button' },
    text: 'اعمال فیلتر',
  });

  filterBar.append(rangeWrapper, sortWrapper, applyButton);

  const table = createTable(
    [
      {
        label: 'کد قطعه',
        render: (row) => createElement('span', { classes: ['code-chip'], text: row.code || '—' }),
      },
      {
        label: 'نام قطعه',
        render: (row) => row.partName || '—',
      },
      {
        label: 'تعداد درخواست',
        render: (row) => row.requestCount?.toLocaleString('fa-IR') ?? '0',
      },
    ],
    { emptyMessage: 'داده‌ای برای نمایش وجود ندارد.' }
  );

  const loadingState = createLoadingState('در حال دریافت آمار...');
  loadingState.hidden = true;

  const pagination = createElement('div', { classes: ['pagination'] });
  const prevButton = createElement('button', {
    classes: ['pagination__button'],
    attrs: { type: 'button' },
    text: 'قبلی',
  });
  const pageInfo = createElement('span', { classes: ['pagination__info'], text: '' });
  const nextButton = createElement('button', {
    classes: ['pagination__button'],
    attrs: { type: 'button' },
    text: 'بعدی',
  });
  pagination.append(prevButton, pageInfo, nextButton);

  container.append(heading, filterBar, table.wrapper, pagination, loadingState);

  let currentPage = 1;
  const pageSize = 20;
  let totalPages = 1;
  let totalItems = 0;
  let isLoading = false;

  rangeSelect.value = '1m';
  sortSelect.value = 'desc';

  function updatePagination() {
    pageInfo.textContent = `صفحه ${currentPage} از ${totalPages}`;
    prevButton.disabled = isLoading || currentPage <= 1;
    nextButton.disabled = isLoading || currentPage >= totalPages;
    pagination.hidden = totalItems <= pageSize;
  }

  async function loadStats({ page = currentPage, toast = false } = {}) {
    isLoading = true;
    loadingState.hidden = false;
    updatePagination();
    try {
      const response = await api.getCodeStats({
        range: rangeSelect.value,
        sort: sortSelect.value,
        page,
        pageSize,
      });
      const items = response?.items ?? [];
      currentPage = response?.page ?? page;
      totalItems = response?.total ?? items.length;
      totalPages = response?.pages ?? Math.max(1, Math.ceil(totalItems / pageSize));
      table.update(items);
      if (toast) {
        renderToast({ message: 'آمار کدها به‌روزرسانی شد.' });
      }
    } catch (error) {
      console.error('Failed to load code statistics', error);
      table.update([]);
      totalItems = 0;
      totalPages = 1;
      renderToast({ message: 'بارگذاری آمار ناموفق بود.', type: 'error' });
    } finally {
      isLoading = false;
      loadingState.hidden = true;
      updatePagination();
    }
  }

  function handlePrev() {
    if (currentPage > 1 && !isLoading) {
      loadStats({ page: currentPage - 1 });
    }
  }

  function handleNext() {
    if (currentPage < totalPages && !isLoading) {
      loadStats({ page: currentPage + 1 });
    }
  }

  function applyFilters() {
    if (isLoading) return;
    currentPage = 1;
    loadStats({ page: 1, toast: true });
  }

  prevButton.addEventListener('click', handlePrev);
  nextButton.addEventListener('click', handleNext);
  rangeSelect.addEventListener('change', applyFilters);
  sortSelect.addEventListener('change', applyFilters);
  applyButton.addEventListener('click', applyFilters);

  await loadStats();

  return {
    refresh() {
      return loadStats({ page: currentPage, toast: true });
    },
    destroy() {
      table.update([]);
      prevButton.removeEventListener('click', handlePrev);
      nextButton.removeEventListener('click', handleNext);
      rangeSelect.removeEventListener('change', applyFilters);
      sortSelect.removeEventListener('change', applyFilters);
      applyButton.removeEventListener('click', applyFilters);
    },
  };
}
