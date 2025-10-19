/**
 * UI helper utilities and reusable widgets for the control panel.
 */

export function escapeHTML(value) {
  if (value == null) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function createElement(tag, { classes = [], attrs = {}, text, html } = {}) {
  const element = document.createElement(tag);
  if (classes.length) {
    element.classList.add(...classes);
  }

  Object.entries(attrs).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    if (typeof value === 'boolean') {
      if (value) {
        element.setAttribute(key, '');
      }
      return;
    }
    element.setAttribute(key, value);
  });

  if (text !== undefined) {
    element.textContent = text;
  }

  if (html !== undefined) {
    element.innerHTML = html;
  }

  return element;
}

export function clearChildren(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

export function debounce(fn, delay = 250) {
  let timer = null;
  return function debounced(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

export function formatRelativeTime(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  const formatter = new Intl.RelativeTimeFormat('fa', { numeric: 'auto' });
  const now = new Date();
  const diff = date.getTime() - now.getTime();
  const diffMinutes = Math.round(diff / (1000 * 60));
  if (Math.abs(diffMinutes) < 60) {
    return formatter.format(diffMinutes, 'minute');
  }
  const diffHours = Math.round(diff / (1000 * 60 * 60));
  if (Math.abs(diffHours) < 24) {
    return formatter.format(diffHours, 'hour');
  }
  const diffDays = Math.round(diff / (1000 * 60 * 60 * 24));
  return formatter.format(diffDays, 'day');
}

export function formatDateTime(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  return new Intl.DateTimeFormat('fa-IR', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function createToggle({ id, checked = false, onChange, label }) {
  const wrapper = createElement('label', { classes: ['toggle'], attrs: { for: id } });
  const input = createElement('input', {
    attrs: { type: 'checkbox', id, 'aria-label': label ?? 'toggle' },
  });
  input.checked = Boolean(checked);
  const slider = createElement('span', { classes: ['toggle__slider'], attrs: { 'aria-hidden': 'true' } });

  input.addEventListener('change', (event) => {
    onChange?.(event.target.checked, event);
  });

  wrapper.append(input, slider);
  return { wrapper, input };
}

let toastTimer = null;

export function renderToast({ message, type = 'success', duration = 3200 }) {
  if (!message) return;
  const root = document.getElementById('toast-root') ?? document.body;
  root.innerHTML = '';
  const toast = createElement('div', { classes: ['toast', `toast--${type}`], text: message });
  root.appendChild(toast);

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.remove();
  }, duration);
}

export function renderModal({ title, content, onClose }) {
  const backdrop = createElement('div', { classes: ['modal-backdrop'], attrs: { role: 'dialog', 'aria-modal': 'true' } });
  const modal = createElement('div', { classes: ['modal'] });
  const header = createElement('div', { classes: ['modal__header'] });
  const titleEl = createElement('h3', { classes: ['modal__title'], text: title });
  const closeButton = createElement('button', {
    classes: ['modal__close'],
    attrs: { type: 'button', 'aria-label': 'بستن' },
    html: '&times;',
  });
  const body = createElement('div', { classes: ['modal__body'] });

  const close = () => {
    backdrop.remove();
    onClose?.();
  };

  closeButton.addEventListener('click', close);
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) {
      close();
    }
  });

  if (content instanceof HTMLElement) {
    body.appendChild(content);
  } else if (Array.isArray(content)) {
    content.forEach((node) => body.append(node));
  } else if (typeof content === 'string') {
    body.innerHTML = content;
  }

  header.append(titleEl, closeButton);
  modal.append(header, body);
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);

  return { modal, body, close };
}

export function createTable(columns, { emptyMessage = 'داده‌ای وجود ندارد.' } = {}) {
  const wrapper = createElement('div', { classes: ['table-wrapper'] });
  const table = createElement('table');
  const thead = createElement('thead');
  const headerRow = createElement('tr');
  columns.forEach((column) => {
    const th = createElement('th', { text: column.label });
    if (column.width) {
      th.style.width = column.width;
    }
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  const tbody = createElement('tbody');
  table.append(thead, tbody);
  wrapper.appendChild(table);

  const renderRows = (rows) => {
    clearChildren(tbody);
    if (!rows || !rows.length) {
      const emptyRow = createElement('tr');
      const cell = createElement('td', {
        attrs: { colspan: columns.length },
      });
      cell.appendChild(createElement('div', { classes: ['empty-state'], text: emptyMessage }));
      emptyRow.appendChild(cell);
      tbody.appendChild(emptyRow);
      return;
    }

    rows.forEach((row) => {
      const tr = createElement('tr');
      columns.forEach((column) => {
        const td = createElement('td');
        if (column.render) {
          const content = column.render(row, td);
          if (content instanceof HTMLElement) {
            td.appendChild(content);
          } else if (typeof content === 'string') {
            td.innerHTML = content;
          }
        } else {
          td.textContent = row[column.field] ?? '';
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  };

  return { wrapper, update: renderRows, table, tbody };
}

export function createBadge(text, variant = 'default') {
  const classes = ['badge'];
  if (variant === 'success') classes.push('badge--success');
  if (variant === 'danger') classes.push('badge--danger');
  return createElement('span', { classes, text });
}

export function createLoadingState(message = 'در حال بارگذاری...') {
  const container = createElement('div', { classes: ['empty-state'], text: message });
  return container;
}

export function createToolbar({ title, actions = [], search }) {
  const wrapper = createElement('div', { classes: ['toolbar'] });
  if (title) {
    const heading = createElement('h3', { classes: ['section-heading__title'], text: title });
    wrapper.appendChild(heading);
  }

  if (search) {
    const input = createElement('input', {
      attrs: {
        type: 'search',
        placeholder: search.placeholder ?? 'جستجو...',
        'aria-label': search.ariaLabel ?? 'جستجو',
      },
    });
    search.input = input;
    wrapper.appendChild(input);
  }

  if (actions.length) {
    const actionsContainer = createElement('div', { classes: ['toolbar__actions'] });
    actions.forEach((action) => {
      const btn = createElement('button', {
        classes: ['btn', ...(action.variant ? [`btn--${action.variant}`] : ['btn--primary'])],
        attrs: { type: 'button' },
        text: action.label,
      });
      btn.addEventListener('click', action.onClick);
      actionsContainer.appendChild(btn);
    });
    wrapper.appendChild(actionsContainer);
  }

  return wrapper;
}

export function renderWorkingHoursList(workingHours) {
  const list = createElement('ul', { classes: ['list-inline'] });
  const order = [5, 6, 0, 1, 2, 3, 4];
  const dayNames = {
    0: 'دوشنبه',
    1: 'سه‌شنبه',
    2: 'چهارشنبه',
    3: 'پنجشنبه',
    4: 'جمعه',
    5: 'شنبه',
    6: 'یکشنبه',
  };
  const weekly = Array.isArray(workingHours?.weekly) ? [...workingHours.weekly] : [];
  weekly.sort((a, b) => {
    const aIndex = order.indexOf(a.day);
    const bIndex = order.indexOf(b.day);
    const safeA = aIndex === -1 ? order.length : aIndex;
    const safeB = bIndex === -1 ? order.length : bIndex;
    return safeA - safeB;
  });
  weekly.forEach((item) => {
    const dayName = dayNames[item.day] || `روز ${item.day}`;
    const text =
      item.open && item.close
        ? `${dayName}: ${item.open} – ${item.close}`
        : `${dayName}: تعطیل`;
    list.appendChild(createElement('li', { text }));
  });
  return list;
}
