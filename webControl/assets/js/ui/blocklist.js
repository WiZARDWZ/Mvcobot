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
      placeholder: 'جستجوی شناسه کاربر...',
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
      {
        label: 'شناسه کاربر',
        render: (row) => row.userId?.toLocaleString('fa-IR') ?? row.id,
      },
      {
        label: 'پلتفرم',
        render: (row) => createBadge(PLATFORM_LABELS[row.platform] ?? row.platform, 'default'),
      },
      {
        label: 'تاریخ ثبت',
        render: (row) => formatDateTime(row.createdAtISO) || '—',
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
    { emptyMessage: 'کاربری در لیست مسدود یافت نشد.' }
  );

  const loadingState = createLoadingState('در حال دریافت لیست...');

  const layout = createElement('div', { classes: ['page-layout'] });
  const blocklistCard = createElement('section', { classes: ['card'] });
  blocklistCard.append(toolbar, table.wrapper, loadingState);
  layout.append(blocklistCard);
  container.append(layout);

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
      return [String(item.userId ?? ''), item.phoneOrUser]
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

    const userControl = createElement('div', { classes: ['form-control'] });
    userControl.append(
      createElement('label', { attrs: { for: 'block-user-id' }, text: 'شناسه کاربر تلگرام' }),
      createElement('input', {
        attrs: {
          id: 'block-user-id',
          name: 'userId',
          required: true,
          type: 'number',
          inputmode: 'numeric',
          placeholder: 'مثال: 123456789',
        },
      }),
      createElement('p', {
        classes: ['form-control__hint'],
        text: 'شناسه عددی کاربر را وارد کنید تا دسترسی او به ربات قطع شود.',
      })
    );

    form.append(userControl);

    const { close } = renderModal({
      title: 'افزودن کاربر به لیست',
      content: form,
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const formData = new FormData(form);
      const userIdValue = String(formData.get('userId') || '').trim();
      const userId = Number(userIdValue);
      if (!userIdValue || Number.isNaN(userId)) {
        renderToast({ message: 'شناسه کاربر باید عدد باشد.', type: 'error' });
        return;
      }
      const payload = { userId };
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
    const confirmed = window.confirm(`آیا از حذف کاربر ${item.userId ?? item.phoneOrUser} مطمئن هستید؟`);
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
