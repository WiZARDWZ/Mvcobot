import { api } from '../api.js';
import {
  createElement,
  createLoadingState,
  createTable,
  debounce,
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

function formatCompactCode(code) {
  const value = typeof code === 'string' ? code.trim() : '';
  if (!value) {
    return '—';
  }
  const threshold = 10;
  if (value.length <= threshold) {
    return value;
  }
  const prefix = value.slice(0, 3);
  const suffix = value.slice(-3);
  return `${prefix}…${suffix}`;
}

function createCodeChip(code) {
  const value = typeof code === 'string' ? code.trim() : '';
  const compact = formatCompactCode(value);
  const chip = createElement('span', { classes: ['code-chip'] });

  if (!value) {
    chip.textContent = '—';
    chip.classList.add('code-chip--empty');
    return chip;
  }

  chip.textContent = compact;
  chip.setAttribute('title', value);

  if (compact !== value) {
    chip.classList.add('code-chip--interactive');
    chip.setAttribute('role', 'button');
    chip.setAttribute('tabindex', '0');
    chip.dataset.compact = compact;
    chip.dataset.full = value;
    chip.dataset.expanded = 'false';

    const toggle = () => {
      const expanded = chip.dataset.expanded === 'true';
      if (expanded) {
        chip.textContent = chip.dataset.compact;
        chip.dataset.expanded = 'false';
      } else {
        chip.textContent = chip.dataset.full;
        chip.dataset.expanded = 'true';
      }
    };

    chip.addEventListener('click', toggle);
    chip.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggle();
      }
    });
    chip.addEventListener('blur', () => {
      if (chip.dataset.expanded === 'true') {
        chip.textContent = chip.dataset.compact;
        chip.dataset.expanded = 'false';
      }
    });
  }

  return chip;
}

function resolvePartName(name) {
  if (!name) return '—';
  const text = String(name).trim();
  if (!text || text === '-') {
    return '—';
  }
  return text;
}

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

  const searchWrapper = createElement('label', { classes: ['filter-bar__group'] });
  const searchLabel = createElement('span', { classes: ['filter-bar__label'], text: 'جستجوی کد' });
  const searchInput = createElement('input', {
    classes: ['filter-bar__input'],
    attrs: {
      type: 'text',
      placeholder: 'مثال: 12345-67890',
      inputmode: 'text',
      autocomplete: 'off',
    },
  });
  searchWrapper.append(searchLabel, searchInput);

  const applyButton = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'button' },
    text: 'اعمال فیلتر',
  });

  const refreshButton = createElement('button', {
    classes: ['btn', 'btn--ghost'],
    attrs: { type: 'button' },
    text: 'بازخوانی نام قطعه‌ها',
  });

  const actionsWrapper = createElement('div', { classes: ['filter-bar__actions'] });
  actionsWrapper.append(refreshButton, applyButton);

  filterBar.append(rangeWrapper, sortWrapper, searchWrapper, actionsWrapper);

  const table = createTable(
    [
      {
        label: 'کد قطعه',
        render: (row) => createCodeChip(row.code),
      },
      {
        label: 'نام قطعه',
        render: (row) => resolvePartName(row.partName),
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

  const layout = createElement('div', { classes: ['page-layout'] });
  const statsCard = createElement('section', { classes: ['card'] });
  statsCard.append(heading, filterBar, table.wrapper, pagination, loadingState);
  layout.append(statsCard);
  container.append(layout);

  let currentPage = 1;
  const pageSize = 20;
  let totalPages = 1;
  let totalItems = 0;
  let isLoading = false;
  let isRefreshingNames = false;

  rangeSelect.value = '1m';
  sortSelect.value = 'desc';

  function updatePagination() {
    pageInfo.textContent = `صفحه ${currentPage} از ${totalPages}`;
    prevButton.disabled = isLoading || currentPage <= 1;
    nextButton.disabled = isLoading || currentPage >= totalPages;
    pagination.hidden = totalItems <= pageSize;
    applyButton.disabled = isLoading;
    refreshButton.disabled = isLoading || isRefreshingNames;
  }

  async function loadStats({ page = currentPage, toast = false } = {}) {
    isLoading = true;
    loadingState.hidden = false;
    updatePagination();
    const searchTerm = searchInput.value.trim();
    let succeeded = false;
    try {
      const response = await api.getCodeStats({
        range: rangeSelect.value,
        sort: sortSelect.value,
        page,
        pageSize,
        search: searchTerm,
      });
      const items = response?.items ?? [];
      currentPage = response?.page ?? page;
      totalItems = response?.total ?? items.length;
      totalPages = response?.pages ?? Math.max(1, Math.ceil(totalItems / pageSize));
      table.update(items);
      succeeded = true;
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
    return succeeded;
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

  const onSearchInput = debounce(() => {
    if (isLoading) return;
    currentPage = 1;
    loadStats({ page: 1 });
  }, 350);

  function handleSearchKeyDown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      applyFilters();
    }
  }

  async function handleRefreshNames() {
    if (isRefreshingNames || isLoading) {
      return;
    }
    isRefreshingNames = true;
    updatePagination();
    try {
      const response = await api.refreshCodeNames();
      currentPage = 1;
      const refreshed = await loadStats({ page: 1 });
      if (refreshed) {
        const updatedCount = Number(response?.updated ?? 0);
        const message =
          updatedCount > 0
            ? `${updatedCount.toLocaleString('fa-IR')} نام قطعه به‌روزرسانی شد.`
            : 'نام تازه‌ای برای بروزرسانی یافت نشد.';
        renderToast({ message, type: updatedCount > 0 ? 'success' : 'warning' });
      }
    } catch (error) {
      console.error('Failed to refresh code names', error);
      renderToast({ message: 'بازخوانی نام قطعه‌ها ناموفق بود.', type: 'error' });
    } finally {
      isRefreshingNames = false;
      updatePagination();
    }
  }

  prevButton.addEventListener('click', handlePrev);
  nextButton.addEventListener('click', handleNext);
  rangeSelect.addEventListener('change', applyFilters);
  sortSelect.addEventListener('change', applyFilters);
  applyButton.addEventListener('click', applyFilters);
  searchInput.addEventListener('input', onSearchInput);
  searchInput.addEventListener('keydown', handleSearchKeyDown);
  refreshButton.addEventListener('click', handleRefreshNames);

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
      searchInput.removeEventListener('input', onSearchInput);
      searchInput.removeEventListener('keydown', handleSearchKeyDown);
      refreshButton.removeEventListener('click', handleRefreshNames);
    },
  };
}
