/**
 * Settings tab module with redesigned layout and interactions.
 */
import { api } from '../api.js';
import {
  createElement,
  createLoadingState,
  createToggle,
  renderToast,
} from './components.js';

const DAY_LABELS = [
  { day: 5, label: 'شنبه' },
  { day: 6, label: 'یکشنبه' },
  { day: 0, label: 'دوشنبه' },
  { day: 1, label: 'سه‌شنبه' },
  { day: 2, label: 'چهارشنبه' },
  { day: 3, label: 'پنجشنبه' },
  { day: 4, label: 'جمعه' },
];

const PLATFORM_CONFIG = [
  { key: 'telegram', label: 'تلگرام' },
  { key: 'privateTelegram', label: 'تلگرام خصوصی' },
  { key: 'whatsapp', label: 'واتساپ' },
];

function createTabs(items) {
  const root = createElement('div', { classes: ['tabs'] });
  const list = createElement('div', {
    classes: ['tabs__list'],
    attrs: { role: 'tablist' },
  });
  const panelsContainer = createElement('div', { classes: ['tabs__panels'] });
  root.append(list, panelsContainer);

  const panelMap = new Map();
  let activeId = null;

  const activate = (id) => {
    if (!panelMap.has(id) || id === activeId) {
      return;
    }
    panelMap.forEach(({ panel, trigger }, key) => {
      const isActive = key === id;
      trigger.classList.toggle('is-active', isActive);
      trigger.setAttribute('aria-selected', isActive ? 'true' : 'false');
      panel.hidden = !isActive;
    });
    activeId = id;
  };

  items.forEach((item, index) => {
    const trigger = createElement('button', {
      classes: ['tabs__trigger'],
      text: item.label,
      attrs: {
        type: 'button',
        role: 'tab',
        id: `tab-${item.id}`,
        'aria-controls': `panel-${item.id}`,
      },
    });
    const panel = createElement('div', {
      classes: ['tabs__panel'],
      attrs: {
        role: 'tabpanel',
        id: `panel-${item.id}`,
        'aria-labelledby': `tab-${item.id}`,
      },
    });

    if (index === 0) {
      trigger.classList.add('is-active');
      trigger.setAttribute('aria-selected', 'true');
      panel.hidden = false;
      activeId = item.id;
    } else {
      trigger.setAttribute('aria-selected', 'false');
      panel.hidden = true;
    }

    trigger.addEventListener('click', () => activate(item.id));

    list.appendChild(trigger);
    panelsContainer.appendChild(panel);
    panelMap.set(item.id, { panel, trigger });
  });

  return {
    root,
    getPanel(id) {
      return panelMap.get(id)?.panel ?? null;
    },
    activate,
  };
}

function createTooltip(text) {
  if (!text) return null;
  return createElement('span', {
    classes: ['form-control__tooltip'],
    attrs: {
      'data-tooltip': text,
      tabindex: '0',
      role: 'note',
      'aria-label': text,
    },
    text: '؟',
  });
}

export async function mount(container) {
  const disposables = [];
  const platformToggleRegistry = {
    telegram: [],
    whatsapp: [],
    privateTelegram: [],
  };

  let settings = null;
  let dayControls = [];

  const header = createElement('div', { classes: ['section-heading'] });
  header.append(
    createElement('h3', { classes: ['section-heading__title'], text: 'تنظیمات ربات' })
  );

  const quickCard = createElement('div', {
    classes: ['card', 'quick-settings'],
  });
  quickCard.append(
    createElement('h4', { classes: ['card__title'], text: 'تنظیمات سریع' }),
    createElement('p', {
      classes: ['card__description'],
      text: 'دسترسی سریع به مهم‌ترین وضعیت‌ها و امکان اعمال بازه زمانی عمومی برای تمام روزها.',
    })
  );

  const quickStats = createElement('div', { classes: ['quick-settings__stats'] });

  const quickStatusValue = createElement('span', {
    classes: ['quick-settings__value'],
    text: '—',
  });
  const quickStatusHint = createElement('span', {
    classes: ['quick-settings__hint'],
    text: 'پلتفرم‌های فعال: —',
  });
  const quickStatus = createElement('div', { classes: ['quick-settings__stat'] });
  quickStatus.append(
    createElement('span', {
      classes: ['quick-settings__label'],
      text: 'وضعیت کلی ربات',
    }),
    quickStatusValue,
    quickStatusHint
  );

  const quickTimezoneValue = createElement('span', {
    classes: ['quick-settings__value'],
    text: 'Asia/Tehran',
  });
  const quickTimezone = createElement('div', { classes: ['quick-settings__stat'] });
  quickTimezone.append(
    createElement('span', {
      classes: ['quick-settings__label'],
      text: 'منطقه زمانی فعال',
    }),
    quickTimezoneValue,
    createElement('span', {
      classes: ['quick-settings__hint'],
      text: 'برای هماهنگی با ساعات کاری ربات استفاده می‌شود.',
    })
  );

  const quickLimitValue = createElement('span', {
    classes: ['quick-settings__value'],
    text: '—',
  });
  const quickLimit = createElement('div', { classes: ['quick-settings__stat'] });
  quickLimit.append(
    createElement('span', {
      classes: ['quick-settings__label'],
      text: 'محدودیت استعلام',
    }),
    quickLimitValue,
    createElement('span', {
      classes: ['quick-settings__hint'],
      text: 'در هر ۲۴ ساعت چند پیام مجاز است؟',
    })
  );

  quickStats.append(quickStatus, quickTimezone, quickLimit);

  const quickPlatforms = createElement('div', {
    classes: ['quick-settings__platforms'],
  });
  quickPlatforms.append(
    createElement('h5', {
      classes: ['quick-settings__section-title'],
      text: 'پلتفرم‌های فعال',
    }),
    createElement('p', {
      classes: ['quick-settings__section-hint'],
      text: 'سوئیچ‌ها را برای فعال‌سازی یا توقف سریع هر پلتفرم جابجا کنید.',
    })
  );
  const quickPlatformList = createElement('div', { classes: ['platform-grid', 'platform-grid--compact'] });
  quickPlatforms.append(quickPlatformList);

  const quickHours = createElement('div', { classes: ['quick-settings__block'] });
  quickHours.append(
    createElement('h5', {
      classes: ['quick-settings__section-title'],
      text: 'اعمال بازه زمانی عمومی',
    }),
    createElement('p', {
      classes: ['quick-settings__section-hint'],
      text: 'برای مثال اگر تمام روزها بین ۰۹:۰۰ تا ۱۸:۰۰ فعال هستند، این بازه را یک‌بار ثبت کنید.',
    })
  );

  const quickHoursForm = createElement('form', { classes: ['quick-settings__form'] });
  const quickHoursGrid = createElement('div', {
    classes: ['form-grid', 'form-grid--compact'],
  });
  const quickStartControl = createElement('div', { classes: ['form-control'] });
  const quickStartLabel = createElement('div', { classes: ['form-control__label'] });
  const quickStartInput = createElement('input', {
    attrs: {
      type: 'time',
      id: 'quick-start',
      name: 'quick-start',
      'aria-label': 'ساعت شروع عمومی',
    },
  });
  quickStartLabel.append(
    createElement('label', { attrs: { for: 'quick-start' }, text: 'شروع' }),
    createTooltip('ساعت شروعی که برای تمام روزهای فعال اعمال می‌شود.')
  );
  quickStartControl.append(
    quickStartLabel,
    quickStartInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'مثلاً 09:00',
    })
  );

  const quickEndControl = createElement('div', { classes: ['form-control'] });
  const quickEndLabel = createElement('div', { classes: ['form-control__label'] });
  const quickEndInput = createElement('input', {
    attrs: {
      type: 'time',
      id: 'quick-end',
      name: 'quick-end',
      'aria-label': 'ساعت پایان عمومی',
    },
  });
  quickEndLabel.append(
    createElement('label', { attrs: { for: 'quick-end' }, text: 'پایان' }),
    createTooltip('ساعت پایان پاسخ‌گویی برای تمام روزهای فعال.')
  );
  quickEndControl.append(
    quickEndLabel,
    quickEndInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'مثلاً 18:00',
    })
  );

  quickHoursGrid.append(quickStartControl, quickEndControl);
  const quickHoursActions = createElement('div', { classes: ['form-actions', 'form-actions--inline'] });
  const quickHoursSubmit = createElement('button', {
    classes: ['btn', 'btn--secondary'],
    attrs: { type: 'submit' },
    text: 'اعمال برای تمام روزها',
  });
  quickHoursActions.append(quickHoursSubmit);
  quickHoursForm.append(quickHoursGrid, quickHoursActions);
  quickHours.append(quickHoursForm);

  quickCard.append(quickStats, quickPlatforms, quickHours);

  const tabs = createTabs([
    { id: 'working-hours', label: 'ساعات کاری' },
    { id: 'messaging', label: 'پیام‌ها و محدودیت‌ها' },
    { id: 'platforms', label: 'پلتفرم‌ها' },
    { id: 'advanced', label: 'تنظیمات پیشرفته' },
  ]);

  const loadingState = createLoadingState('در حال دریافت تنظیمات...');
  loadingState.hidden = true;

  container.append(header, quickCard, tabs.root, loadingState);

  const workingPanel = tabs.getPanel('working-hours');
  const messagingPanel = tabs.getPanel('messaging');
  const platformsPanel = tabs.getPanel('platforms');
  const advancedPanel = tabs.getPanel('advanced');

  const workingCard = createElement('div', { classes: ['card', 'settings-card'] });
  workingCard.append(
    createElement('h4', { classes: ['card__title'], text: 'ساعات کاری ربات' }),
    createElement('p', {
      classes: ['card__description'],
      text: 'بازه زمانی فعال‌بودن ربات را تنظیم کنید. می‌توانید روزهای تعطیل را غیرفعال کنید.',
    })
  );

  const workingHoursForm = createElement('form', { classes: ['settings-form'] });
  const timezoneControl = createElement('div', { classes: ['form-control'] });
  const timezoneLabel = createElement('div', { classes: ['form-control__label'] });
  timezoneLabel.append(
    createElement('label', {
      attrs: { for: 'timezone-input' },
      text: 'منطقه زمانی',
    }),
    createTooltip('نمونه: Asia/Tehran – برای محاسبه صحیح ساعات کاری مورد استفاده قرار می‌گیرد.')
  );
  const timezoneInput = createElement('input', {
    attrs: {
      type: 'text',
      id: 'timezone-input',
      name: 'timezone',
      required: true,
      placeholder: 'مثلاً: Asia/Tehran',
    },
  });
  timezoneControl.append(
    timezoneLabel,
    timezoneInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'از استاندارد IANA استفاده کنید.',
    })
  );

  const scheduleWrapper = createElement('div', {
    classes: ['schedule-table__wrapper'],
  });
  const scheduleTable = createElement('table', { classes: ['schedule-table'] });
  const scheduleHead = createElement('thead');
  const scheduleHeadRow = createElement('tr');
  ['روز هفته', 'شروع', 'پایان', 'وضعیت'].forEach((title) => {
    scheduleHeadRow.appendChild(createElement('th', { text: title }));
  });
  scheduleHead.appendChild(scheduleHeadRow);
  const scheduleBody = createElement('tbody');
  scheduleTable.append(scheduleHead, scheduleBody);
  scheduleWrapper.append(scheduleTable);

  dayControls = DAY_LABELS.map((item) => {
    const row = createElement('tr');
    const dayCell = createElement('td', { text: item.label });

    const openInput = createElement('input', {
      attrs: {
        type: 'time',
        name: `open-${item.day}`,
        'aria-label': `ساعت شروع ${item.label}`,
      },
    });
    const openCell = createElement('td');
    const openWrapper = createElement('div', { classes: ['time-field'] });
    openWrapper.append(openInput);
    openCell.append(openWrapper);

    const closeInput = createElement('input', {
      attrs: {
        type: 'time',
        name: `close-${item.day}`,
        'aria-label': `ساعت پایان ${item.label}`,
      },
    });
    const closeCell = createElement('td');
    const closeWrapper = createElement('div', { classes: ['time-field'] });
    closeWrapper.append(closeInput);
    closeCell.append(closeWrapper);

    const statusCell = createElement('td');
    const statusToggle = createToggle({
      id: `day-toggle-${item.day}`,
      checked: true,
      label: `وضعیت روز ${item.label}`,
    });
    statusToggle.wrapper.classList.add('toggle--compact');
    const statusLabel = createElement('span', {
      classes: ['status-toggle__label'],
      text: 'فعال',
    });
    const statusWrapper = createElement('div', { classes: ['status-toggle'] });
    statusWrapper.append(statusToggle.wrapper, statusLabel);
    statusCell.append(statusWrapper);

    const updateDisabledState = () => {
      const isActive = statusToggle.input.checked;
      row.dataset.state = isActive ? 'active' : 'inactive';
      openInput.disabled = !isActive;
      closeInput.disabled = !isActive;
      statusLabel.textContent = isActive ? 'فعال' : 'غیرفعال';
      statusWrapper.setAttribute('data-state', isActive ? 'active' : 'inactive');
      if (!isActive) {
        openInput.value = '';
        closeInput.value = '';
      }
    };

    const onToggleChange = () => {
      updateDisabledState();
    };
    statusToggle.input.addEventListener('change', onToggleChange);
    disposables.push(() => {
      statusToggle.input.removeEventListener('change', onToggleChange);
    });

    updateDisabledState();

    row.append(dayCell, openCell, closeCell, statusCell);
    scheduleBody.appendChild(row);

    return {
      day: item.day,
      row,
      openInput,
      closeInput,
      toggle: statusToggle.input,
      updateDisabledState,
    };
  });

  const workingActions = createElement('div', { classes: ['form-actions'] });
  const workingHoursSubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره ساعات کاری',
  });
  workingActions.append(workingHoursSubmit);

  workingHoursForm.append(timezoneControl, scheduleWrapper, workingActions);
  workingCard.append(workingHoursForm);
  workingPanel?.append(workingCard);

  const messagingCard = createElement('div', { classes: ['card', 'settings-card'] });
  messagingCard.append(
    createElement('h4', { classes: ['card__title'], text: 'پیام‌ها و محدودیت‌ها' }),
    createElement('p', {
      classes: ['card__description'],
      text: 'بازه استراحت ناهار، محدودیت پیام‌ها و متن‌های اطلاع‌رسانی را تنظیم کنید.',
    })
  );

  const lunchForm = createElement('form', { classes: ['settings-form'] });
  const lunchGrid = createElement('div', {
    classes: ['form-grid', 'form-grid--two-column'],
  });
  const lunchStartControl = createElement('div', { classes: ['form-control'] });
  const lunchStartLabel = createElement('div', { classes: ['form-control__label'] });
  const lunchStartInput = createElement('input', {
    attrs: { type: 'time', id: 'lunch-start', name: 'lunch-start' },
  });
  lunchStartLabel.append(
    createElement('label', { attrs: { for: 'lunch-start' }, text: 'شروع ناهار' }),
    createTooltip('در این بازه ربات پاسخگو نخواهد بود.')
  );
  lunchStartControl.append(
    lunchStartLabel,
    lunchStartInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'مثلاً 13:00',
    })
  );

  const lunchEndControl = createElement('div', { classes: ['form-control'] });
  const lunchEndLabel = createElement('div', { classes: ['form-control__label'] });
  const lunchEndInput = createElement('input', {
    attrs: { type: 'time', id: 'lunch-end', name: 'lunch-end' },
  });
  lunchEndLabel.append(
    createElement('label', { attrs: { for: 'lunch-end' }, text: 'پایان ناهار' }),
    createTooltip('زمانی که ربات دوباره فعال می‌شود.')
  );
  lunchEndControl.append(lunchEndLabel, lunchEndInput);
  lunchGrid.append(lunchStartControl, lunchEndControl);

  const lunchActions = createElement('div', { classes: ['form-actions'] });
  const lunchSubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره بازه ناهار',
  });
  lunchActions.append(lunchSubmit);
  lunchForm.append(lunchGrid, lunchActions);

  const queryForm = createElement('form', { classes: ['settings-form'] });
  const queryControl = createElement('div', { classes: ['form-control'] });
  const queryLabel = createElement('div', { classes: ['form-control__label'] });
  queryLabel.append(
    createElement('label', {
      attrs: { for: 'query-limit' },
      text: 'تعداد مجاز در ۲۴ ساعت',
    }),
    createTooltip('عدد کل پیام‌های مجاز در هر ۲۴ ساعت. برای حذف محدودیت خالی بگذارید.')
  );
  const queryLimitInput = createElement('input', {
    attrs: {
      type: 'number',
      id: 'query-limit',
      name: 'query-limit',
      min: '0',
      inputmode: 'numeric',
      placeholder: 'مثلاً: 120 پیام در ۲۴ ساعت',
    },
  });
  queryControl.append(
    queryLabel,
    queryLimitInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'برای حذف محدودیت، مقدار را خالی بگذارید.',
    })
  );
  const queryActions = createElement('div', { classes: ['form-actions'] });
  const querySubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره محدودیت',
  });
  queryActions.append(querySubmit);
  queryForm.append(queryControl, queryActions);

  const deliveryForm = createElement('form', { classes: ['settings-form'] });
  const deliveryGrid = createElement('div', {
    classes: ['form-grid', 'form-grid--two-column'],
  });
  const deliveryBeforeControl = createElement('div', { classes: ['form-control'] });
  const deliveryBeforeLabel = createElement('div', { classes: ['form-control__label'] });
  const deliveryBeforeInput = createElement('textarea', {
    attrs: {
      id: 'delivery-before',
      name: 'delivery-before',
      rows: '3',
      placeholder: 'مثلاً: سفارش‌ها پیش از ساعت ۱۶ ارسال می‌شوند.',
    },
  });
  deliveryBeforeLabel.append(
    createElement('label', { attrs: { for: 'delivery-before' }, text: 'متن قبل از ساعت مشخص' }),
    createTooltip('پیامی که پیش از ساعت تغییر برای کاربر ارسال می‌شود.')
  );
  deliveryBeforeControl.append(deliveryBeforeLabel, deliveryBeforeInput);

  const deliveryAfterControl = createElement('div', { classes: ['form-control'] });
  const deliveryAfterLabel = createElement('div', { classes: ['form-control__label'] });
  const deliveryAfterInput = createElement('textarea', {
    attrs: {
      id: 'delivery-after',
      name: 'delivery-after',
      rows: '3',
      placeholder: 'مثلاً: سفارش‌ها پس از ساعت ۱۶ روز بعد ارسال می‌شوند.',
    },
  });
  deliveryAfterLabel.append(
    createElement('label', { attrs: { for: 'delivery-after' }, text: 'متن بعد از ساعت مشخص' }),
    createTooltip('پیامی که پس از ساعت تغییر برای کاربر ارسال می‌شود.')
  );
  deliveryAfterControl.append(deliveryAfterLabel, deliveryAfterInput);

  const deliveryTimeControl = createElement('div', { classes: ['form-control'] });
  const deliveryTimeLabel = createElement('div', { classes: ['form-control__label'] });
  const changeoverInput = createElement('input', {
    attrs: {
      type: 'time',
      id: 'changeover-hour',
      name: 'changeover-hour',
    },
  });
  deliveryTimeLabel.append(
    createElement('label', { attrs: { for: 'changeover-hour' }, text: 'ساعت تغییر متن' }),
    createTooltip('ساعتی که متن قبل و بعد از آن جابجا می‌شود.')
  );
  deliveryTimeControl.append(
    deliveryTimeLabel,
    changeoverInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'مثلاً 16:00',
    })
  );

  deliveryGrid.append(deliveryBeforeControl, deliveryAfterControl, deliveryTimeControl);
  const deliveryActions = createElement('div', { classes: ['form-actions'] });
  const deliverySubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره متن تحویل کالا',
  });
  deliveryActions.append(deliverySubmit);
  deliveryForm.append(deliveryGrid, deliveryActions);

  messagingCard.append(lunchForm, queryForm, deliveryForm);
  messagingPanel?.append(messagingCard);

  const platformCard = createElement('div', { classes: ['card', 'settings-card'] });
  platformCard.append(
    createElement('h4', { classes: ['card__title'], text: 'پلتفرم‌های در دسترس' }),
    createElement('p', {
      classes: ['card__description'],
      text: 'کنترل فعال یا غیرفعال بودن هر پلتفرم پاسخ‌گویی ربات.',
    })
  );
  const platformList = createElement('div', { classes: ['platform-grid'] });
  platformCard.append(platformList);
  platformsPanel?.append(platformCard);

  const advancedCard = createElement('div', { classes: ['card', 'settings-card'] });
  advancedCard.append(
    createElement('h4', { classes: ['card__title'], text: 'تنظیمات پیشرفته' }),
    createElement('p', {
      classes: ['card__description'],
      text: 'در صورت نیاز، کش داده‌ها را پاک‌سازی کنید تا داده‌ها از ربات به‌روزرسانی شوند.',
    })
  );

  const invalidateButton = createElement('button', {
    classes: ['btn', 'btn--ghost'],
    attrs: { type: 'button' },
    text: 'پاک‌سازی کش',
  });
  advancedCard.append(invalidateButton);
  advancedPanel?.append(advancedCard);

  const buildPlatformToggles = (target, variant = 'default') => {
    PLATFORM_CONFIG.forEach((platform) => {
      const row = createElement('div', {
        classes: ['platform-row', variant === 'compact' ? 'platform-row--compact' : ''],
      });
      const title = createElement('div', {
        classes: ['platform-row__title'],
        text: platform.label,
      });
      const status = createElement('span', {
        classes: ['status-chip'],
        text: 'در حال بررسی',
      });
      status.dataset.state = 'active';
      const toggle = createToggle({
        id: `${platform.key}-${variant}-toggle`,
        checked: true,
        label: `سوئیچ ${platform.label}`,
      });
      const stateLabel = createElement('span', {
        classes: ['platform-row__state'],
        text: 'فعال',
      });
      stateLabel.dataset.state = 'active';
      if (variant === 'compact') {
        toggle.wrapper.classList.add('toggle--compact');
      }
      const control = createElement('div', { classes: ['platform-row__control'] });
      control.append(toggle.wrapper, stateLabel);

      const onToggleChange = (event) => {
        handlePlatformChange(platform.key, event.target.checked, toggle.input);
      };
      toggle.input.addEventListener('change', onToggleChange);
      disposables.push(() => toggle.input.removeEventListener('change', onToggleChange));

      platformToggleRegistry[platform.key].push({
        input: toggle.input,
        stateLabel,
        status,
        row,
      });

      row.append(title, status, control);
      row.dataset.state = 'active';
      target.append(row);
    });
  };

  buildPlatformToggles(platformList);
  buildPlatformToggles(quickPlatformList, 'compact');

  const updatePlatformVisuals = (platformsState) => {
    PLATFORM_CONFIG.forEach((platform) => {
      const isActive = platformsState?.[platform.key] ?? true;
      platformToggleRegistry[platform.key].forEach((entry) => {
        entry.input.checked = isActive;
        entry.stateLabel.textContent = isActive ? 'فعال' : 'غیرفعال';
        entry.stateLabel.dataset.state = isActive ? 'active' : 'inactive';
        entry.status.textContent = isActive ? '✅ فعال' : '⭕ غیرفعال';
        entry.status.dataset.state = isActive ? 'active' : 'inactive';
        entry.row.dataset.state = isActive ? 'active' : 'inactive';
      });
    });
  };

  const setPlatformBusy = (platform, busy) => {
    platformToggleRegistry[platform].forEach((entry) => {
      entry.input.disabled = busy;
    });
  };

  const updateQuickSummary = () => {
    const timezone = settings?.timezone ?? 'Asia/Tehran';
    quickTimezoneValue.textContent = timezone;

    const platformsState = settings?.platforms ?? {};
    const activePlatforms = PLATFORM_CONFIG.filter((platform) => platformsState[platform.key]);
    const activeCount = activePlatforms.length;
    const statusState = activeCount > 0 ? 'active' : 'inactive';
    quickStatusValue.textContent = activeCount > 0 ? 'فعال' : 'متوقف';
    quickStatusValue.dataset.state = statusState;
    quickStatusHint.textContent = `پلتفرم‌های فعال: ${
      activeCount ? activePlatforms.map((item) => item.label).join('، ') : 'هیچ‌کدام'
    }`;

    if (typeof settings?.queryLimit === 'number' && settings.queryLimit > 0) {
      quickLimitValue.textContent = `${settings.queryLimit.toLocaleString('fa-IR')} پیام / ۲۴ ساعت`;
    } else {
      quickLimitValue.textContent = 'بدون محدودیت';
    }
  };

  const onQuickHoursSubmit = (event) => {
    event.preventDefault();
    const start = quickStartInput.value;
    const end = quickEndInput.value;
    if (!start || !end) {
      renderToast({
        message: 'برای اعمال بازه، هر دو مقدار شروع و پایان را وارد کنید.',
        type: 'warning',
      });
      return;
    }
    dayControls.forEach((control) => {
      control.toggle.checked = true;
      control.openInput.value = start;
      control.closeInput.value = end;
      control.updateDisabledState();
    });
    renderToast({
      message: 'بازه زمانی روی تمام روزهای فعال اعمال شد. برای ذخیره، دکمه مربوطه را بزنید.',
    });
  };
  quickHoursForm.addEventListener('submit', onQuickHoursSubmit);
  disposables.push(() => quickHoursForm.removeEventListener('submit', onQuickHoursSubmit));

  const loadSettings = async (showToast = false) => {
    loadingState.hidden = false;
    try {
      settings = await api.getSettings();
      applySettings();
      if (showToast) {
        renderToast({ message: 'تنظیمات به‌روزرسانی شد.' });
      }
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      loadingState.hidden = true;
    }
  };

  const applySettings = () => {
    timezoneInput.value = settings?.timezone ?? 'Asia/Tehran';
    dayControls.forEach((control) => {
      const current = settings?.weekly?.find((item) => item.day === control.day) ?? {
        open: null,
        close: null,
      };
      const hasHours = Boolean(current.open && current.close);
      control.toggle.checked = hasHours;
      control.openInput.value = current.open ?? '';
      control.closeInput.value = current.close ?? '';
      control.updateDisabledState();
    });

    const lunchBreak = settings?.lunchBreak ?? {};
    lunchStartInput.value = lunchBreak.start ?? '';
    lunchEndInput.value = lunchBreak.end ?? '';

    if (typeof settings?.queryLimit === 'number' && settings.queryLimit > 0) {
      queryLimitInput.value = settings.queryLimit;
    } else {
      queryLimitInput.value = '';
    }

    const deliveryInfo = settings?.deliveryInfo ?? {};
    deliveryBeforeInput.value = deliveryInfo.before ?? '';
    deliveryAfterInput.value = deliveryInfo.after ?? '';
    changeoverInput.value = deliveryInfo.changeover ?? '';

    updatePlatformVisuals(settings?.platforms);
    updateQuickSummary();
  };

  const onWorkingHoursSubmit = async (event) => {
    event.preventDefault();
    const weekly = dayControls.map((control) => ({
      day: control.day,
      open: control.toggle.checked ? control.openInput.value || null : null,
      close: control.toggle.checked ? control.closeInput.value || null : null,
    }));
    const payload = {
      timezone: timezoneInput.value.trim() || 'Asia/Tehran',
      weekly,
    };
    try {
      workingHoursSubmit.disabled = true;
      settings = await api.updateSettings(payload);
      applySettings();
      renderToast({ message: 'ساعات کاری ذخیره شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      workingHoursSubmit.disabled = false;
    }
  };
  workingHoursForm.addEventListener('submit', onWorkingHoursSubmit);

  const onLunchSubmit = async (event) => {
    event.preventDefault();
    const payload = {
      lunchBreak: {
        start: lunchStartInput.value || null,
        end: lunchEndInput.value || null,
      },
    };
    try {
      lunchSubmit.disabled = true;
      settings = await api.updateSettings(payload);
      applySettings();
      renderToast({ message: 'بازه ناهار ذخیره شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      lunchSubmit.disabled = false;
    }
  };
  lunchForm.addEventListener('submit', onLunchSubmit);

  const onQuerySubmit = async (event) => {
    event.preventDefault();
    const raw = queryLimitInput.value.trim();
    let limitValue = null;
    if (raw !== '') {
      const parsed = Number.parseInt(raw, 10);
      if (Number.isNaN(parsed)) {
        renderToast({ message: 'مقدار واردشده نامعتبر است.', type: 'error' });
        return;
      }
      limitValue = parsed;
    }
    try {
      querySubmit.disabled = true;
      settings = await api.updateSettings({ queryLimit: limitValue });
      applySettings();
      renderToast({ message: 'محدودیت استعلام ذخیره شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      querySubmit.disabled = false;
    }
  };
  queryForm.addEventListener('submit', onQuerySubmit);

  const onDeliverySubmit = async (event) => {
    event.preventDefault();
    const payload = {
      deliveryInfo: {
        before: deliveryBeforeInput.value.trim(),
        after: deliveryAfterInput.value.trim(),
        changeover: changeoverInput.value || null,
      },
    };
    try {
      deliverySubmit.disabled = true;
      settings = await api.updateSettings(payload);
      applySettings();
      renderToast({ message: 'متن تحویل کالا ذخیره شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      deliverySubmit.disabled = false;
    }
  };
  deliveryForm.addEventListener('submit', onDeliverySubmit);

  const handlePlatformChange = async (platform, checked, inputEl) => {
    try {
      setPlatformBusy(platform, true);
      settings = await api.updateSettings({
        platforms: {
          ...(settings?.platforms ?? {}),
          [platform]: checked,
        },
      });
      const configKeyMap = {
        telegram: 'TELEGRAM_ENABLED',
        whatsapp: 'WHATSAPP_ENABLED',
        privateTelegram: 'PRIVATE_TELEGRAM_ENABLED',
      };
      const configKey = configKeyMap[platform];
      if (configKey) {
        window.APP_CONFIG = {
          ...(window.APP_CONFIG ?? {}),
          [configKey]: checked,
        };
      }
      updatePlatformVisuals(settings?.platforms);
      updateQuickSummary();
      const platformLabel = PLATFORM_CONFIG.find((item) => item.key === platform)?.label ?? platform;
      renderToast({
        message: `پلتفرم ${platformLabel} ${checked ? 'فعال' : 'غیرفعال'} شد.`,
      });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
      inputEl.checked = !checked;
      updatePlatformVisuals(settings?.platforms);
    } finally {
      setPlatformBusy(platform, false);
    }
  };

  const onInvalidateClick = async () => {
    try {
      invalidateButton.disabled = true;
      await api.invalidateCache();
      renderToast({ message: 'کش ربات پاک‌سازی شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      invalidateButton.disabled = false;
    }
  };
  invalidateButton.addEventListener('click', onInvalidateClick);

  disposables.push(
    () => workingHoursForm.removeEventListener('submit', onWorkingHoursSubmit),
    () => lunchForm.removeEventListener('submit', onLunchSubmit),
    () => queryForm.removeEventListener('submit', onQuerySubmit),
    () => deliveryForm.removeEventListener('submit', onDeliverySubmit),
    () => invalidateButton.removeEventListener('click', onInvalidateClick)
  );

  await loadSettings();

  return {
    async refresh() {
      await loadSettings(true);
    },
    destroy() {
      disposables.forEach((dispose) => dispose?.());
    },
  };
}
