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
    const aDay = Number(a.day);
    const bDay = Number(b.day);
    const aIndex = order.indexOf(aDay);
    const bIndex = order.indexOf(bDay);
    const safeA = aIndex === -1 ? order.length : aIndex;
    const safeB = bIndex === -1 ? order.length : bIndex;
    return safeA - safeB;
  });
  weekly.forEach((item) => {
    const day = Number(item.day);
    const dayName = dayNames[day] || `روز ${day}`;
    const hasHours = Boolean(item.open && item.close && item.closed !== true);
    const text = hasHours
      ? `${dayName}: ${item.open} – ${item.close}`
      : `${dayName}: تعطیل`;
    list.appendChild(createElement('li', { text }));
  });
  return list;
}

const DEFAULT_NORMALIZE_OPTIONS = {
  trim: true,
  collapseWhitespace: true,
  caseInsensitive: true,
  persianArabicUnify: true,
  stripDiacritics: true,
  normalizeDigits: 'both',
};

const DEFAULT_HIGHLIGHT_OPTIONS = {
  enabled: false,
  tag: 'mark',
  className: '',
};

const DEFAULT_MESSAGES = {
  initial: 'برای فیلتر کردن تایپ کنید.',
  noData: 'داده‌ای برای نمایش وجود ندارد.',
  noResults: 'هیچ نتیجه‌ای یافت نشد.',
};

const LEADING_NON_ALNUM = /^[^\p{L}\p{N}]+/u;

function unifyPersianArabic(text) {
  return text
    .replace(/[كﮎﮏﮐﮑ]/g, 'ک')
    .replace(/[يىۑ]/g, 'ی')
    .replace(/[ۀة]/g, 'ه')
    .replace(/[أإآ]/g, 'ا')
    .replace(/ؤ/g, 'و')
    .replace(/ئ/g, 'ی');
}

function normalizeDigits(text, mode) {
  if (!mode || mode === 'none') {
    return text;
  }
  const persianDigits = '۰۱۲۳۴۵۶۷۸۹';
  const arabicDigits = '٠١٢٣٤٥٦٧٨٩';
  let result = text;
  if (mode === 'persian' || mode === 'both') {
    result = result.replace(/[۰-۹]/g, (ch) => String(persianDigits.indexOf(ch)));
  }
  if (mode === 'arabic' || mode === 'both') {
    result = result.replace(/[٠-٩]/g, (ch) => String(arabicDigits.indexOf(ch)));
  }
  return result;
}

function stripDiacritics(text) {
  try {
    return text
      .normalize('NFKD')
      .replace(/\p{Mn}+/gu, '');
  } catch (error) {
    return text
      .normalize('NFKD')
      .replace(/[\u064B-\u065F\u0610-\u061A\u06D6-\u06ED]+/g, '');
  }
}

function normalizeTextValue(value, options = DEFAULT_NORMALIZE_OPTIONS) {
  if (value == null) {
    return '';
  }
  const settings = { ...DEFAULT_NORMALIZE_OPTIONS, ...options };
  let text = String(value);
  if (settings.trim) {
    text = text.trim();
  }
  if (settings.collapseWhitespace) {
    text = text.replace(/\s+/g, ' ');
  }
  if (settings.persianArabicUnify) {
    text = unifyPersianArabic(text);
  }
  if (settings.normalizeDigits) {
    text = normalizeDigits(text, settings.normalizeDigits);
  }
  if (settings.caseInsensitive) {
    text = text.toLowerCase();
  }
  if (settings.stripDiacritics) {
    text = stripDiacritics(text);
  }
  if (settings.trim) {
    text = text.trim();
  }
  return text;
}

function sanitizeTokenList(tokens) {
  const unique = [];
  tokens.forEach((token) => {
    if (!token) return;
    if (!unique.includes(token)) {
      unique.push(token);
    }
  });
  return unique;
}

function removeLeadingNonAlnum(value) {
  return value.replace(LEADING_NON_ALNUM, '');
}

function formatNumber(value) {
  try {
    return new Intl.NumberFormat('fa-IR').format(value);
  } catch (error) {
    return String(value);
  }
}

function buildHighlightedFragment(text, tokens, highlightOptions, normalizeOptions) {
  const fragment = document.createDocumentFragment();
  const content = text == null ? '' : String(text);
  if (!highlightOptions.enabled || !tokens.length || !content) {
    fragment.append(document.createTextNode(content));
    return fragment;
  }

  const parts = content.split(/(\s+)/);
  const sortedTokens = [...tokens].sort((a, b) => b.length - a.length);

  parts.forEach((part) => {
    if (!part) return;
    if (/^\s+$/.test(part)) {
      fragment.append(document.createTextNode(part));
      return;
    }
    const normalizedPart = normalizeTextValue(part, normalizeOptions);
    const sanitized = removeLeadingNonAlnum(normalizedPart);
    let matchedToken = null;
    sortedTokens.some((token) => {
      if (!token) return false;
      if (sanitized.startsWith(token)) {
        matchedToken = token;
        return true;
      }
      return false;
    });

    if (!matchedToken) {
      fragment.append(document.createTextNode(part));
      return;
    }

    const leadingNormalizedLength = normalizedPart.length - sanitized.length;
    const leadingSlice = part.slice(0, leadingNormalizedLength);
    if (leadingSlice) {
      fragment.append(document.createTextNode(leadingSlice));
    }

    const highlightLength = Math.min(part.length - leadingNormalizedLength, matchedToken.length);
    const HighlightTag = highlightOptions.tag || 'mark';
    const mark = document.createElement(HighlightTag);
    if (highlightOptions.className) {
      highlightOptions.className
        .split(/\s+/)
        .filter(Boolean)
        .forEach((cls) => mark.classList.add(cls));
    }
    mark.textContent = part.slice(leadingNormalizedLength, leadingNormalizedLength + highlightLength);
    fragment.append(mark);

    const rest = part.slice(leadingNormalizedLength + highlightLength);
    if (rest) {
      fragment.append(document.createTextNode(rest));
    }
  });

  return fragment;
}

function matchesField(field, token, matchFromSet) {
  if (!field.normalized) {
    return false;
  }
  if (matchFromSet.has('startOfString')) {
    if (removeLeadingNonAlnum(field.normalized).startsWith(token)) {
      return true;
    }
  }
  if (matchFromSet.has('startOfWord')) {
    return field.words.some((word) => removeLeadingNonAlnum(word).startsWith(token));
  }
  return false;
}

export function createPrefixSearch({
  placeholder = 'جستجو...',
  ariaLabel = 'جستجو',
  searchKey,
  secondaryKeys = [],
  minChars = 1,
  debounceMs = 200,
  maxResults = 50,
  andLogic = true,
  matchFrom = ['startOfString', 'startOfWord'],
  normalize = {},
  highlight = {},
  emptyQueryBehavior = 'all',
  rtlSupport = false,
  messages = {},
  display = {},
} = {}) {
  if (!searchKey) {
    throw new Error('createPrefixSearch requires a searchKey option.');
  }

  const normalizeOptions = { ...DEFAULT_NORMALIZE_OPTIONS, ...normalize };
  const highlightOptions = { ...DEFAULT_HIGHLIGHT_OPTIONS, ...highlight };
  const messageConfig = { ...DEFAULT_MESSAGES, ...messages };
  const matchFromSet = new Set(Array.isArray(matchFrom) ? matchFrom : []);
  if (!matchFromSet.size) {
    matchFromSet.add('startOfString');
  }

  const displayConfig = {
    codeKey: display.codeKey ?? 'code',
    subtitleKey: display.subtitleKey ?? 'subtitle',
    renderExtra: typeof display.renderExtra === 'function' ? display.renderExtra : null,
  };

  const wrapper = createElement('div', { classes: ['prefix-search'] });
  if (rtlSupport) {
    wrapper.setAttribute('dir', 'rtl');
  }

  const input = createElement('input', {
    classes: ['prefix-search__input'],
    attrs: {
      type: 'search',
      placeholder,
      'aria-label': ariaLabel,
      autocomplete: 'off',
      autocapitalize: 'none',
      spellcheck: 'false',
      inputmode: 'search',
    },
  });

  const status = createElement('div', { classes: ['prefix-search__status'], text: messageConfig.initial });
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');

  const resultsList = createElement('ul', { classes: ['prefix-search__results'] });

  wrapper.append(input, status, resultsList);

  let preparedItems = [];
  let tokens = [];

  function renderResults(entries) {
    clearChildren(resultsList);
    const totalCount = preparedItems.length;
    const filteredCount = entries.length;
    const displayCount = Math.min(entries.length, Math.max(0, maxResults || entries.length));
    const hasTokens = tokens.length > 0;

    if (!totalCount) {
      status.textContent = messageConfig.noData;
      resultsList.append(
        createElement('li', {
          classes: ['prefix-search__empty'],
          text: messageConfig.noData,
        })
      );
      return;
    }

    if (!hasTokens && emptyQueryBehavior !== 'all') {
      status.textContent = messageConfig.initial;
      return;
    }

    if (hasTokens && filteredCount === 0) {
      status.textContent = messageConfig.noResults;
      resultsList.append(
        createElement('li', {
          classes: ['prefix-search__empty'],
          text: messageConfig.noResults,
        })
      );
      return;
    }

    const itemsToRender = entries.slice(0, displayCount);

    if (!itemsToRender.length) {
      status.textContent = messageConfig.noData;
      resultsList.append(
        createElement('li', {
          classes: ['prefix-search__empty'],
          text: messageConfig.noData,
        })
      );
      return;
    }

    if (!hasTokens) {
      status.textContent = filteredCount < totalCount
        ? `نمایش ${formatNumber(displayCount)} مورد از ${formatNumber(totalCount)} رکورد`
        : `نمایش ${formatNumber(filteredCount)} رکورد`;
    } else if (filteredCount > displayCount) {
      status.textContent = `نمایش ${formatNumber(displayCount)} مورد از ${formatNumber(filteredCount)} نتیجه یافت‌شده`;
    } else {
      status.textContent = `تعداد نتایج: ${formatNumber(filteredCount)}`;
    }

    itemsToRender.forEach(({ item }) => {
      const li = createElement('li', { classes: ['prefix-search__item'] });
      const header = createElement('div', { classes: ['prefix-search__header'] });

      const titleValue = item?.[searchKey] ?? '';
      const title = document.createElement('span');
      title.classList.add('prefix-search__title');
      title.append(buildHighlightedFragment(titleValue, tokens, highlightOptions, normalizeOptions));
      header.appendChild(title);

      const codeValue = displayConfig.codeKey ? item?.[displayConfig.codeKey] : undefined;
      if (codeValue !== undefined && codeValue !== null && String(codeValue).trim() !== '') {
        const code = document.createElement('span');
        code.classList.add('prefix-search__code');
        code.append(buildHighlightedFragment(codeValue, tokens, highlightOptions, normalizeOptions));
        header.appendChild(code);
      }

      li.appendChild(header);

      const subtitleValue = displayConfig.subtitleKey ? item?.[displayConfig.subtitleKey] : undefined;
      if (subtitleValue !== undefined && subtitleValue !== null && String(subtitleValue).trim() !== '') {
        const subtitle = document.createElement('p');
        subtitle.classList.add('prefix-search__subtitle');
        subtitle.append(buildHighlightedFragment(subtitleValue, tokens, highlightOptions, normalizeOptions));
        li.appendChild(subtitle);
      }

      if (displayConfig.renderExtra) {
        const extra = displayConfig.renderExtra(item, tokens);
        if (extra instanceof Node) {
          li.appendChild(extra);
        }
      }

      resultsList.appendChild(li);
    });
  }

  function applyFilter() {
    const rawQuery = input.value ?? '';
    const normalized = normalizeTextValue(rawQuery, normalizeOptions);
    const characterCount = normalized.replace(/\s+/g, '').length;
    tokens = sanitizeTokenList(normalized.split(' ').filter(Boolean));

    if (tokens.length && characterCount < minChars) {
      tokens = [];
    }

    let entries = [];
    if (!tokens.length) {
      entries = emptyQueryBehavior === 'all' ? preparedItems : [];
    } else {
      entries = preparedItems.filter(({ fields }) => {
        if (!fields.length) return false;
        if (andLogic) {
          return tokens.every((token) => fields.some((field) => matchesField(field, token, matchFromSet)));
        }
        return tokens.some((token) => fields.some((field) => matchesField(field, token, matchFromSet)));
      });
    }

    renderResults(entries);
  }

  const debouncedFilter = debounce(applyFilter, debounceMs);

  const handleInput = () => {
    debouncedFilter();
  };

  const handleSearchEvent = () => {
    applyFilter();
  };

  input.addEventListener('input', handleInput);
  input.addEventListener('search', handleSearchEvent);

  function setItems(items = []) {
    const list = Array.isArray(items) ? items : [];
    preparedItems = list.map((item) => {
      const keys = [searchKey, ...secondaryKeys];
      const fields = keys.map((key) => {
        const rawValue = item?.[key] ?? '';
        const normalized = normalizeTextValue(rawValue, normalizeOptions);
        const words = normalized ? normalized.split(' ') : [];
        return { key, normalized, words };
      });
      return { item, fields };
    });
    applyFilter();
  }

  function clear() {
    input.value = '';
    tokens = [];
    applyFilter();
  }

  function destroy() {
    input.removeEventListener('input', handleInput);
    input.removeEventListener('search', handleSearchEvent);
  }

  return {
    wrapper,
    input,
    setItems,
    clear,
    destroy,
  };
}
