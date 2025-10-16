/**
 * Commands tab module.
 */
import { api } from '../api.js';
import {
  clearChildren,
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

export async function mount(container) {
  const toolbar = createToolbar({
    title: 'مدیریت دستورات',
    search: {
      placeholder: 'جستجوی دستور یا توضیحات...',
      ariaLabel: 'جستجو در دستورات',
    },
    actions: [
      {
        label: 'دستور جدید',
        onClick: () => openCommandModal(),
      },
    ],
  });

  const table = createTable(
    [
      { label: 'دستور', field: 'command' },
      { label: 'توضیحات', field: 'description' },
      {
        label: 'آخرین استفاده',
        render: (row) => formatDateTime(row.lastUsedISO) || '—',
      },
      {
        label: 'وضعیت',
        render: (row) => createBadge(row.enabled ? 'فعال' : 'غیرفعال', row.enabled ? 'success' : 'danger'),
      },
      {
        label: 'عملیات',
        render: (row) => {
          const actions = createElement('div', { classes: ['table-actions'] });
          const editBtn = createElement('button', {
            classes: ['btn', 'btn--ghost'],
            attrs: { type: 'button' },
            text: 'ویرایش',
          });
          editBtn.addEventListener('click', () => openCommandModal(row));

          const toggleBtn = createElement('button', {
            classes: ['btn', row.enabled ? 'btn--danger' : 'btn--primary'],
            attrs: { type: 'button' },
            text: row.enabled ? 'غیرفعال' : 'فعال',
          });
          toggleBtn.addEventListener('click', () => toggleCommand(row));

          const deleteBtn = createElement('button', {
            classes: ['btn', 'btn--danger'],
            attrs: { type: 'button' },
            text: 'حذف',
          });
          deleteBtn.addEventListener('click', () => deleteCommand(row));

          actions.append(editBtn, toggleBtn, deleteBtn);
          return actions;
        },
      },
    ],
    { emptyMessage: 'هنوز دستوری ثبت نشده است.' }
  );

  const loadingState = createLoadingState('در حال دریافت دستورات...');

  container.append(toolbar, table.wrapper, loadingState);

  const searchInput = toolbar.querySelector('input[type="search"]');

  let commands = [];
  let filterTerm = '';

  async function loadCommands(showToast = false) {
    loadingState.hidden = false;
    try {
      commands = await api.getCommands();
      applyFilter();
      if (showToast) {
        renderToast({ message: 'لیست دستورات به‌روزرسانی شد.' });
      }
    } catch (error) {
      console.error('Failed to load commands', error);
      renderToast({ message: error.message, type: 'error' });
      table.update([]);
    } finally {
      loadingState.hidden = true;
    }
  }

  function applyFilter() {
    const term = filterTerm.trim().toLowerCase();
    if (!term) {
      table.update(commands);
      return;
    }
    const filtered = commands.filter((command) => {
      return [command.command, command.description]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(term));
    });
    table.update(filtered);
  }

  const handleSearch = debounce((event) => {
    filterTerm = event.target.value;
    applyFilter();
  }, 200);

  searchInput?.addEventListener('input', handleSearch);

  async function openCommandModal(command) {
    const isEdit = Boolean(command);
    const form = createElement('form');

    const commandControl = createElement('div', { classes: ['form-control'] });
    commandControl.append(
      createElement('label', { attrs: { for: 'command-input' }, text: 'دستور' }),
      createElement('input', {
        attrs: {
          id: 'command-input',
          name: 'command',
          required: true,
          maxlength: 64,
          value: command?.command ?? '',
          placeholder: '/command',
        },
      })
    );

    const descriptionControl = createElement('div', { classes: ['form-control'] });
    descriptionControl.append(
      createElement('label', { attrs: { for: 'command-description' }, text: 'توضیحات' }),
      createElement('textarea', {
        attrs: {
          id: 'command-description',
          name: 'description',
          required: true,
          maxlength: 256,
          rows: 3,
        },
        text: command?.description ?? '',
      })
    );

    const enabledControl = createElement('div', { classes: ['form-control'] });
    const enabledCheckbox = createElement('input', {
      attrs: {
        id: 'command-enabled',
        type: 'checkbox',
        name: 'enabled',
        checked: command?.enabled ?? true,
      },
    });
    enabledCheckbox.checked = command?.enabled ?? true;
    const enabledLabel = createElement('label', {
      attrs: { for: 'command-enabled' },
      text: 'فعال باشد',
    });
    enabledControl.append(enabledLabel, enabledCheckbox);

    form.append(commandControl, descriptionControl, enabledControl);

    const { close } = renderModal({
      title: isEdit ? 'ویرایش دستور' : 'دستور جدید',
      content: form,
    });

    const actions = createElement('div', { classes: ['form-actions'] });
    const cancelBtn = createElement('button', {
      classes: ['btn', 'btn--ghost'],
      attrs: { type: 'button' },
      text: 'لغو',
    });
    cancelBtn.addEventListener('click', () => close());
    const submitBtn = createElement('button', {
      classes: ['btn', 'btn--primary'],
      attrs: { type: 'submit' },
      text: isEdit ? 'ذخیره تغییرات' : 'ایجاد دستور',
    });
    actions.append(cancelBtn, submitBtn);
    form.append(actions);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const formData = new FormData(form);
      const commandValue = String(formData.get('command') || '').trim();
      const descriptionValue = String(formData.get('description') || '').trim();
      const payload = {
        command: commandValue,
        description: descriptionValue,
        enabled: formData.get('enabled') === 'on',
      };
      try {
        if (isEdit) {
          const updated = await api.updateCommand(command.id, payload);
          commands = commands.map((item) => (item.id === command.id ? updated : item));
          renderToast({ message: 'دستور با موفقیت به‌روزرسانی شد.' });
        } else {
          const created = await api.createCommand(payload);
          commands = [created, ...commands];
          renderToast({ message: 'دستور جدید افزوده شد.' });
        }
        applyFilter();
        close();
      } catch (error) {
        renderToast({ message: error.message, type: 'error' });
      }
    });
  }

  async function toggleCommand(command) {
    try {
      const updated = await api.updateCommand(command.id, { enabled: !command.enabled });
      commands = commands.map((item) => (item.id === command.id ? updated : item));
      renderToast({ message: `دستور ${updated.enabled ? 'فعال' : 'غیرفعال'} شد.` });
      applyFilter();
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    }
  }

  async function deleteCommand(command) {
    const confirmed = window.confirm(`حذف ${command.command}؟`);
    if (!confirmed) return;
    try {
      await api.deleteCommand(command.id);
      commands = commands.filter((item) => item.id !== command.id);
      renderToast({ message: 'دستور حذف شد.' });
      applyFilter();
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    }
  }

  await loadCommands();

  return {
    async refresh() {
      await loadCommands(true);
    },
    destroy() {
      searchInput?.removeEventListener('input', handleSearch);
      clearChildren(container);
    },
  };
}
