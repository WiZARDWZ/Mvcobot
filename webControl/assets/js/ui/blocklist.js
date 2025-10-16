/**
 * Blocklist tab module.
 */
import { api } from '../api.js';
import {
  createBadge,
  createElement,
  createLoadingState,
  createTable,
  createToolbar,
  debounce,
  formatDateTime,
  renderModal,
  renderToast,
} from './components.js';

const PLATFORM_LABELS = {
  telegram: 'تلگرام',
  whatsapp: 'واتساپ',
};

export async function mount(container) {
  const toolbar = createToolbar({
    title: 'لیست مسدودسازی',
    search: {
      placeholder: 'جستجوی نام کاربری یا شماره...',
      ariaLabel: 'جستجو در لیست مسدود',
    },
    actions: [
      {
        label: 'افزودن به لیست',
        onClick: () => openBlockModal(),
      },
    ],
  });

  const table = createTable(
    [
      { label: 'شناسه', field: 'id' },
      { label: 'کاربر / شماره', field: 'phoneOrUser' },
      {
        label: 'پلتفرم',
        render: (row) => createBadge(PLATFORM_LABELS[row.platform] ?? row.platform, 'default'),
      },
      {
        label: 'دلیل',
        render: (row) => row.reason || '—',
      },
      {
        label: 'تاریخ ایجاد',
        render: (row) => formatDateTime(row.createdAtISO),
      },
      {
        label: 'عملیات',
        render: (row) => {
          const actions = createElement('div', { classes: ['table-actions'] });
          const removeBtn = createElement('button', {
            classes: ['btn', 'btn--danger'],
            attrs: { type: 'button' },
            text: 'حذف',
          });
          removeBtn.addEventListener('click', () => removeBlock(row));
          actions.append(removeBtn);
          return actions;
        },
      },
    ],
    { emptyMessage: 'شماره یا کاربری مسدود نشده است.' }
  );

  const loadingState = createLoadingState('در حال دریافت لیست...');

  container.append(toolbar, table.wrapper, loadingState);

  const searchInput = toolbar.querySelector('input[type="search"]');
  let entries = [];
  let term = '';

  async function loadBlocklist(showToast = false) {
    loadingState.hidden = false;
    try {
      entries = await api.getBlocklist();
      applyFilter();
      if (showToast) {
        renderToast({ message: 'لیست مسدودسازی به‌روزرسانی شد.' });
      }
    } catch (error) {
      console.error('Failed to load blocklist', error);
      renderToast({ message: error.message, type: 'error' });
      table.update([]);
    } finally {
      loadingState.hidden = true;
    }
  }

  function applyFilter() {
    const value = term.trim().toLowerCase();
    if (!value) {
      table.update(entries);
      return;
    }
    const filtered = entries.filter((item) => {
      return [item.phoneOrUser, item.reason, PLATFORM_LABELS[item.platform]]
        .filter(Boolean)
        .some((field) => field.toLowerCase().includes(value));
    });
    table.update(filtered);
  }

  const handleSearch = debounce((event) => {
    term = event.target.value;
    applyFilter();
  }, 200);

  searchInput?.addEventListener('input', handleSearch);

  async function openBlockModal() {
    const form = createElement('form');

    const phoneControl = createElement('div', { classes: ['form-control'] });
    phoneControl.append(
      createElement('label', { attrs: { for: 'block-phone' }, text: 'کاربر / شماره' }),
      createElement('input', {
        attrs: {
          id: 'block-phone',
          name: 'phoneOrUser',
          required: true,
          placeholder: '@username یا +989123456789',
        },
      })
    );

    const platformControl = createElement('div', { classes: ['form-control'] });
    const select = createElement('select', {
      attrs: { id: 'block-platform', name: 'platform', required: true },
    });
    select.append(
      createElement('option', { attrs: { value: 'telegram' }, text: 'تلگرام' }),
      createElement('option', { attrs: { value: 'whatsapp' }, text: 'واتساپ' })
    );
    platformControl.append(
      createElement('label', { attrs: { for: 'block-platform' }, text: 'پلتفرم' }),
      select
    );

    const reasonControl = createElement('div', { classes: ['form-control'] });
    reasonControl.append(
      createElement('label', { attrs: { for: 'block-reason' }, text: 'دلیل' }),
      createElement('textarea', {
        attrs: {
          id: 'block-reason',
          name: 'reason',
          rows: 3,
          maxlength: 200,
          placeholder: 'توضیح مختصر...',
        },
      })
    );

    form.append(phoneControl, platformControl, reasonControl);

    const { close } = renderModal({
      title: 'افزودن کاربر به لیست',
      content: form,
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const formData = new FormData(form);
      const payload = {
        phoneOrUser: String(formData.get('phoneOrUser') || '').trim(),
        platform: formData.get('platform'),
        reason: String(formData.get('reason') || '').trim(),
      };
      try {
        const created = await api.addBlockItem(payload);
        entries = [created, ...entries];
        applyFilter();
        renderToast({ message: 'مورد جدید اضافه شد.' });
        close();
      } catch (error) {
        renderToast({ message: error.message, type: 'error' });
      }
    });

    const submitButton = createElement('button', {
      classes: ['btn', 'btn--primary'],
      attrs: { type: 'submit' },
      text: 'ذخیره',
    });
    const actions = createElement('div', { classes: ['form-actions'] });
    actions.append(submitButton);
    form.append(actions);

  }

  async function removeBlock(item) {
    const confirmed = window.confirm(`آیا از حذف ${item.phoneOrUser} مطمئن هستید؟`);
    if (!confirmed) return;
    try {
      await api.removeBlockItem(item.id);
      entries = entries.filter((entry) => entry.id !== item.id);
      applyFilter();
      renderToast({ message: 'مورد حذف شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    }
  }

  await loadBlocklist();

  return {
    async refresh() {
      await loadBlocklist(true);
    },
    destroy() {
      searchInput?.removeEventListener('input', handleSearch);
    },
  };
}
