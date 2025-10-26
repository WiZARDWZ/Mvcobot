import { api } from '../api.js';
import {
  createElement,
  createLoadingState,
  createTable,
  debounce,
  renderModal,
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

const PEAK_PERIOD_OPTIONS = [
  { value: 'day', label: 'روز' },
  { value: 'month', label: 'ماه' },
  { value: 'year', label: 'سال' },
];

function createCodeChip(code) {
  const value = typeof code === 'string' ? code.trim() : '';
  const chip = createElement('span', { classes: ['code-chip'] });

  if (!value) {
    chip.textContent = '—';
    chip.classList.add('code-chip--empty');
    return chip;
  }

  chip.textContent = value;
  chip.setAttribute('title', value);
  chip.setAttribute('dir', 'ltr');

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
  const rangeWrapper = createElement('label', { classes: ['filter-bar__group'] });
  const rangeLabel = createElement('span', {
    classes: ['filter-bar__label'],
    text: 'بازه زمانی',
  });
  const rangeSelect = createElement('select', { classes: ['filter-bar__select'] });
  RANGE_OPTIONS.forEach((option) => {
    const opt = createElement('option', { text: option.label, attrs: { value: option.value } });
    rangeSelect.appendChild(opt);
  });
  rangeWrapper.append(rangeLabel, rangeSelect);

  const sortWrapper = createElement('label', { classes: ['filter-bar__group'] });
  const sortLabel = createElement('span', {
    classes: ['filter-bar__label'],
    text: 'مرتب‌سازی',
  });
  const sortSelect = createElement('select', { classes: ['filter-bar__select'] });
  SORT_OPTIONS.forEach((option) => {
    const opt = createElement('option', { text: option.label, attrs: { value: option.value } });
    sortSelect.appendChild(opt);
  });
  sortWrapper.append(sortLabel, sortSelect);

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
  searchInput.setAttribute('dir', 'ltr');
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

  const exportButton = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'button' },
  });
  const exportSpinner = createElement('span', {
    classes: ['button-spinner'],
    attrs: { 'aria-hidden': 'true' },
  });
  const exportLabel = createElement('span', {
    classes: ['btn__label'],
    text: 'خروجی اکسل',
  });
  exportButton.append(exportSpinner, exportLabel);

  const actionsBar = createElement('div', { classes: ['stats-actions'] });
  actionsBar.append(exportButton);

  layout.append(statsCard, actionsBar);
  container.append(layout);

  let currentPage = 1;
  const pageSize = 20;
  let totalPages = 1;
  let totalItems = 0;
  let isLoading = false;
  let isRefreshingNames = false;

  function sanitizeFileName(value, fallback) {
    const base = (value ?? '').toString().trim() || fallback || 'گزارش-آمار';
    const cleaned = base.replace(/[\\/:*?"<>|]+/g, '-');
    const normalized = cleaned.replace(/\.(xlsx?|XLSX?)$/i, '');
    const safe = normalized || 'گزارش-آمار';
    return `${safe}.xlsx`;
  }

  function triggerDownload(blob, fileName) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    window.setTimeout(() => {
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    }, 0);
  }

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

  function openExportModal() {
    const suffix = Math.random().toString(16).slice(2);
    const today = new Date().toISOString().slice(0, 10);
    const defaultFileName = sanitizeFileName('', `گزارش-آمار-${today}`);

    const form = createElement('form', { classes: ['export-modal__form'] });

    const dateRow = createElement('div', { classes: ['export-modal__row'] });
    const dateRowLabel = createElement('label', {
      attrs: { for: `export-date-from-${suffix}` },
      text: 'بازه‌ی تاریخ',
    });
    const dateInputs = createElement('div', { classes: ['export-modal__inputs'] });

    const dateFromField = createElement('div', { classes: ['export-modal__field'] });
    const dateFromLabel = createElement('label', {
      attrs: { for: `export-date-from-${suffix}` },
      text: 'از تاریخ',
    });
    const dateFromInput = createElement('input', {
      attrs: {
        type: 'date',
        id: `export-date-from-${suffix}`,
        name: 'dateFrom',
      },
    });
    dateFromField.append(dateFromLabel, dateFromInput);

    const dateToField = createElement('div', { classes: ['export-modal__field'] });
    const dateToLabel = createElement('label', {
      attrs: { for: `export-date-to-${suffix}` },
      text: 'تا تاریخ',
    });
    const dateToInput = createElement('input', {
      attrs: {
        type: 'date',
        id: `export-date-to-${suffix}`,
        name: 'dateTo',
      },
    });
    dateToField.append(dateToLabel, dateToInput);

    dateInputs.append(dateFromField, dateToField);
    dateRow.append(dateRowLabel, dateInputs);

    const detailsRow = createElement('div', { classes: ['export-modal__row'] });
    const detailsLabel = createElement('label', {
      attrs: { for: `export-mother-${suffix}` },
      text: 'مشخصات کالا',
    });
    const detailsInputs = createElement('div', { classes: ['export-modal__inputs'] });

    const motherCodeField = createElement('div', { classes: ['export-modal__field'] });
    const motherCodeLabel = createElement('label', {
      attrs: { for: `export-mother-${suffix}` },
      text: 'کد مادر (قبل از ساده‌سازی)',
    });
    const motherCodeInput = createElement('input', {
      attrs: {
        type: 'text',
        id: `export-mother-${suffix}`,
        name: 'motherCode',
        placeholder: 'مثال: 12345-67890',
        autocomplete: 'off',
      },
    });
    motherCodeInput.setAttribute('dir', 'ltr');
    motherCodeField.append(motherCodeLabel, motherCodeInput);

    const productNameField = createElement('div', { classes: ['export-modal__field'] });
    const productNameLabel = createElement('label', {
      attrs: { for: `export-product-${suffix}` },
      text: 'نام کالا',
    });
    const productNameInput = createElement('input', {
      attrs: {
        type: 'text',
        id: `export-product-${suffix}`,
        name: 'productName',
        placeholder: 'مثال: سنسور اکسیژن',
        autocomplete: 'off',
      },
    });
    productNameField.append(productNameLabel, productNameInput);

    detailsInputs.append(motherCodeField, productNameField);
    detailsRow.append(detailsLabel, detailsInputs);

    const requestRow = createElement('div', { classes: ['export-modal__row'] });
    const requestLabel = createElement('label', {
      attrs: { for: `export-request-${suffix}` },
      text: 'اطلاعات آماری',
    });
    const requestInputs = createElement('div', { classes: ['export-modal__inputs'] });

    const requestCountField = createElement('div', { classes: ['export-modal__field'] });
    const requestCountLabel = createElement('label', {
      attrs: { for: `export-request-${suffix}` },
      text: 'تعداد درخواست',
    });
    const requestCountInput = createElement('input', {
      attrs: {
        type: 'number',
        id: `export-request-${suffix}`,
        name: 'requestCount',
        min: '0',
        step: '1',
        placeholder: 'مثال: 120',
        inputmode: 'numeric',
      },
    });
    requestCountField.append(requestCountLabel, requestCountInput);

    const peakSelect = createElement('select', {
      attrs: {
        id: `export-peak-${suffix}`,
        name: 'peakPeriod',
      },
    });
    PEAK_PERIOD_OPTIONS.forEach((option) => {
      const opt = createElement('option', {
        text: option.label,
        attrs: { value: option.value },
      });
      peakSelect.appendChild(opt);
    });
    peakSelect.value = 'day';
    requestInputs.append(requestCountField);
    requestRow.append(requestLabel, requestInputs);

    const columnsRow = createElement('div', { classes: ['export-modal__row'] });
    const columnsTitle = createElement('span', {
      classes: ['export-modal__row-title'],
      text: 'ستون‌های خروجی اکسل',
    });
    const columnsInputs = createElement('div', { classes: ['export-modal__checkboxes'] });

    function createColumnCheckbox({ id, name, label }) {
      const field = createElement('label', {
        classes: ['export-modal__checkbox'],
        attrs: { for: `${id}-${suffix}` },
      });
      const checkbox = createElement('input', {
        attrs: {
          type: 'checkbox',
          id: `${id}-${suffix}`,
          name,
        },
      });
      checkbox.checked = true;
      const caption = createElement('span', { classes: ['export-modal__checkbox-label'], text: label });
      field.append(checkbox, caption);
      return { field, checkbox };
    }

    const motherColumn = createColumnCheckbox({
      id: 'export-column-mother',
      name: 'includeMotherCode',
      label: 'کد مادر (قبل از ساده‌سازی)',
    });
    const productColumn = createColumnCheckbox({
      id: 'export-column-product',
      name: 'includeProductName',
      label: 'نام کالا',
    });
    const requestColumn = createColumnCheckbox({
      id: 'export-column-requests',
      name: 'includeRequestCount',
      label: 'تعداد درخواست',
    });
    const peakColumn = createColumnCheckbox({
      id: 'export-column-peak',
      name: 'includePeakPeriod',
      label: 'ستون بازه زمانی با بیشترین درخواست',
    });

    const peakControls = createElement('div', { classes: ['export-modal__checkbox-extra'] });
    const peakControlsLabel = createElement('label', {
      attrs: { for: `export-peak-${suffix}` },
      text: 'نوع بازه (روز / ماه / سال)',
    });
    peakControls.append(peakControlsLabel, peakSelect);
    peakColumn.field.appendChild(peakControls);

    columnsInputs.append(
      motherColumn.field,
      productColumn.field,
      requestColumn.field,
      peakColumn.field
    );
    columnsRow.append(columnsTitle, columnsInputs);

    const syncPeakControls = () => {
      peakSelect.disabled = !peakColumn.checkbox.checked;
      peakControlsLabel.classList.toggle('is-disabled', peakSelect.disabled);
    };

    peakColumn.checkbox.addEventListener('change', syncPeakControls);
    syncPeakControls();

    const fileField = createElement('div', { classes: ['export-modal__field'] });
    const fileLabel = createElement('label', {
      attrs: { for: `export-file-${suffix}` },
      text: 'نام فایل خروجی اکسل',
    });
    const fileInput = createElement('input', {
      attrs: {
        type: 'text',
        id: `export-file-${suffix}`,
        name: 'fileName',
        placeholder: 'مثال: report.xlsx',
        autocomplete: 'off',
      },
    });
    fileInput.value = defaultFileName;
    fileInput.setAttribute('dir', 'ltr');
    fileField.append(fileLabel, fileInput);

    const hint = createElement('p', {
      classes: ['export-modal__hint'],
      text: 'در صورت وارد نکردن پسوند ‎.xlsx‎، به صورت خودکار به انتهای نام فایل افزوده می‌شود.',
    });

    const actions = createElement('div', { classes: ['export-modal__actions'] });
    const cancelButton = createElement('button', {
      classes: ['btn', 'btn--ghost'],
      attrs: { type: 'button' },
      text: 'انصراف',
    });
    const downloadButton = createElement('button', {
      classes: ['btn', 'btn--primary'],
      attrs: { type: 'submit' },
    });
    const downloadSpinner = createElement('span', {
      classes: ['button-spinner'],
      attrs: { 'aria-hidden': 'true' },
    });
    const downloadLabel = createElement('span', {
      classes: ['btn__label'],
      text: 'دریافت خروجی',
    });
    downloadButton.append(downloadSpinner, downloadLabel);
    actions.append(cancelButton, downloadButton);

    form.append(dateRow, detailsRow, requestRow, columnsRow, fileField, hint, actions);

    let isSubmitting = false;

    const setSubmitting = (state) => {
      isSubmitting = state;
      downloadButton.classList.toggle('is-loading', state);
      downloadButton.disabled = state;
      cancelButton.disabled = state;
      [
        dateFromInput,
        dateToInput,
        motherCodeInput,
        productNameInput,
        requestCountInput,
        peakSelect,
        fileInput,
        motherColumn.checkbox,
        productColumn.checkbox,
        requestColumn.checkbox,
        peakColumn.checkbox,
      ].forEach((input) => {
        input.disabled = state;
      });
      if (!state) {
        syncPeakControls();
      }
    };

    const handleCancel = (event) => {
      event.preventDefault();
      closeModal();
    };

    const handleSubmit = async (event) => {
      event.preventDefault();
      if (isSubmitting) return;

      const formData = new FormData(form);
      const rawRequestCount = formData.get('requestCount');
      let normalizedRequestCount = null;
      if (rawRequestCount !== null && rawRequestCount !== '') {
        const numericValue = Number(rawRequestCount);
        if (Number.isNaN(numericValue)) {
          renderToast({ message: 'مقدار تعداد درخواست معتبر نیست.', type: 'error' });
          return;
        }
        normalizedRequestCount = numericValue;
      }

      const peakPeriodValue = peakSelect.value || formData.get('peakPeriod') || 'day';

      const payload = {
        dateFrom: formData.get('dateFrom') || null,
        dateTo: formData.get('dateTo') || null,
        motherCode: (formData.get('motherCode') || '').toString().trim(),
        productName: (formData.get('productName') || '').toString().trim(),
        requestCount: normalizedRequestCount,
        peakPeriod: peakPeriodValue,
        includeMotherCode: formData.has('includeMotherCode'),
        includeProductName: formData.has('includeProductName'),
        includeRequestCount: formData.has('includeRequestCount'),
        includePeakPeriod: formData.has('includePeakPeriod'),
        fileName: sanitizeFileName(formData.get('fileName'), defaultFileName),
      };

      if (payload.dateFrom && payload.dateTo) {
        const fromDate = new Date(payload.dateFrom);
        const toDate = new Date(payload.dateTo);
        if (!Number.isNaN(fromDate.valueOf()) && !Number.isNaN(toDate.valueOf()) && fromDate > toDate) {
          renderToast({ message: 'تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.', type: 'error' });
          return;
        }
      }

      setSubmitting(true);
      try {
        const result = await api.exportCodeStatsToExcel(payload);
        if (!result || !(result.blob instanceof Blob)) {
          throw new Error('Invalid export payload');
        }
        const fileName = result.fileName || payload.fileName;
        triggerDownload(result.blob, fileName);
        renderToast({ message: 'خروجی اکسل با موفقیت آماده شد.' });
        closeModal();
      } catch (error) {
        console.error('Failed to export code statistics', error);
        renderToast({ message: 'دریافت خروجی ناموفق بود.', type: 'error' });
        setSubmitting(false);
      }
    };

    const closeModal = () => {
      cancelButton.removeEventListener('click', handleCancel);
      form.removeEventListener('submit', handleSubmit);
      peakColumn.checkbox.removeEventListener('change', syncPeakControls);
      modalHandle.close();
    };

    const modalHandle = renderModal({
      title: 'دریافت خروجی اکسل',
      content: form,
      onClose: () => {
        cancelButton.removeEventListener('click', handleCancel);
        form.removeEventListener('submit', handleSubmit);
        peakColumn.checkbox.removeEventListener('change', syncPeakControls);
      },
    });

    cancelButton.addEventListener('click', handleCancel);
    form.addEventListener('submit', handleSubmit);
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
  exportButton.addEventListener('click', openExportModal);

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
      exportButton.removeEventListener('click', openExportModal);
    },
  };
}
