/**
 * Settings tab module.
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

export async function mount(container) {
  const header = createElement('div', { classes: ['section-heading'] });
  header.append(
    createElement('h3', { classes: ['section-heading__title'], text: 'تنظیمات ربات' })
  );

  const workingHoursCard = createElement('div', { classes: ['card'] });
  workingHoursCard.append(
    createElement('h4', { classes: ['section-heading__title'], text: 'ساعات کاری' })
  );
  const workingHoursForm = createElement('form');
  workingHoursForm.classList.add('working-hours');
  const timezoneControl = createElement('div', { classes: ['form-control'] });
  const timezoneInput = createElement('input', {
    attrs: { type: 'text', id: 'timezone-input', name: 'timezone', required: true },
  });
  timezoneControl.append(
    createElement('label', { attrs: { for: 'timezone-input' }, text: 'منطقه زمانی' }),
    timezoneInput
  );
  workingHoursForm.append(timezoneControl);

  const dayControls = DAY_LABELS.map((item) => {
    const row = createElement('div', { classes: ['working-hours__row'] });
    const label = createElement('span', { classes: ['working-hours__label'], text: item.label });
    const times = createElement('div', { classes: ['working-hours__times'] });
    const openInput = createElement('input', {
      attrs: { type: 'time', name: `open-${item.day}` },
    });
    const closeInput = createElement('input', {
      attrs: { type: 'time', name: `close-${item.day}` },
    });
    const closedWrapper = createElement('label', { classes: ['working-hours__closed'] });
    const closedCheckbox = createElement('input', {
      attrs: { type: 'checkbox', name: `closed-${item.day}` },
    });
    closedWrapper.append(closedCheckbox, document.createTextNode('تعطیل'));

    const openLabel = createElement('span', { text: 'از' });
    const closeLabel = createElement('span', { text: 'تا' });

    times.append(openLabel, openInput, closeLabel, closeInput);
    row.append(label, times, closedWrapper);
    workingHoursForm.append(row);

    const updateDisabledState = () => {
      const closed = closedCheckbox.checked;
      openInput.disabled = closed;
      closeInput.disabled = closed;
      if (closed) {
        openInput.value = '';
        closeInput.value = '';
      }
    };
    const changeHandler = () => updateDisabledState();
    closedCheckbox.addEventListener('change', changeHandler);

    return {
      day: item.day,
      row,
      openInput,
      closeInput,
      closedCheckbox,
      updateDisabledState,
      dispose() {
        closedCheckbox.removeEventListener('change', changeHandler);
      },
    };
  });

  const workingHoursActions = createElement('div', { classes: ['form-actions'] });
  const workingHoursSubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره ساعات کاری',
  });
  workingHoursActions.append(workingHoursSubmit);
  workingHoursForm.append(workingHoursActions);
  workingHoursCard.append(workingHoursForm);

  const operationsCard = createElement('div', { classes: ['card'] });
  operationsCard.append(
    createElement('h4', { classes: ['section-heading__title'], text: 'تنظیمات پیام‌ها و محدودیت‌ها' })
  );

  const lunchGroup = createElement('div', { classes: ['settings-card__group'] });
  lunchGroup.append(
    createElement('h5', { classes: ['settings-card__subtitle'], text: 'استراحت ناهار' })
  );
  const lunchForm = createElement('form', { classes: ['settings-form'] });
  const lunchGrid = createElement('div', { classes: ['form-grid'] });
  const lunchStartControl = createElement('div', { classes: ['form-control'] });
  const lunchStartInput = createElement('input', {
    attrs: { type: 'time', id: 'lunch-start', name: 'lunch-start' },
  });
  lunchStartControl.append(
    createElement('label', { attrs: { for: 'lunch-start' }, text: 'شروع ناهار' }),
    lunchStartInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'در این بازه ربات پاسخ‌گو نخواهد بود.',
    })
  );
  const lunchEndControl = createElement('div', { classes: ['form-control'] });
  const lunchEndInput = createElement('input', {
    attrs: { type: 'time', id: 'lunch-end', name: 'lunch-end' },
  });
  lunchEndControl.append(
    createElement('label', { attrs: { for: 'lunch-end' }, text: 'پایان ناهار' }),
    lunchEndInput
  );
  lunchGrid.append(lunchStartControl, lunchEndControl);
  lunchForm.append(lunchGrid);
  const lunchActions = createElement('div', { classes: ['form-actions'] });
  const lunchSubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره بازه ناهار',
  });
  lunchActions.append(lunchSubmit);
  lunchForm.append(lunchActions);
  lunchGroup.append(lunchForm);

  const queryGroup = createElement('div', { classes: ['settings-card__group'] });
  queryGroup.append(
    createElement('h5', { classes: ['settings-card__subtitle'], text: 'محدودیت استعلام' })
  );
  const queryForm = createElement('form', { classes: ['settings-form'] });
  const queryControl = createElement('div', { classes: ['form-control'] });
  const queryLimitInput = createElement('input', {
    attrs: {
      type: 'number',
      id: 'query-limit',
      name: 'query-limit',
      min: '0',
      inputmode: 'numeric',
    },
  });
  queryControl.append(
    createElement('label', { attrs: { for: 'query-limit' }, text: 'تعداد مجاز در ۲۴ ساعت' }),
    queryLimitInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'برای حذف محدودیت، مقدار را خالی بگذارید.',
    })
  );
  queryForm.append(queryControl);
  const queryActions = createElement('div', { classes: ['form-actions'] });
  const querySubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره محدودیت',
  });
  queryActions.append(querySubmit);
  queryForm.append(queryActions);
  queryGroup.append(queryForm);

  const deliveryGroup = createElement('div', { classes: ['settings-card__group'] });
  deliveryGroup.append(
    createElement('h5', { classes: ['settings-card__subtitle'], text: 'متن اطلاع‌رسانی تحویل کالا' })
  );
  const deliveryForm = createElement('form', { classes: ['settings-form'] });
  const deliveryBeforeControl = createElement('div', { classes: ['form-control'] });
  const deliveryBeforeInput = createElement('textarea', {
    attrs: { id: 'delivery-before', name: 'delivery-before', rows: '3' },
  });
  deliveryBeforeControl.append(
    createElement('label', { attrs: { for: 'delivery-before' }, text: 'متن قبل از ساعت مشخص' }),
    deliveryBeforeInput
  );
  const deliveryAfterControl = createElement('div', { classes: ['form-control'] });
  const deliveryAfterInput = createElement('textarea', {
    attrs: { id: 'delivery-after', name: 'delivery-after', rows: '3' },
  });
  deliveryAfterControl.append(
    createElement('label', { attrs: { for: 'delivery-after' }, text: 'متن بعد از ساعت مشخص' }),
    deliveryAfterInput
  );
  const deliveryTimeControl = createElement('div', { classes: ['form-control'] });
  const changeoverInput = createElement('input', {
    attrs: { type: 'time', id: 'changeover-hour', name: 'changeover-hour' },
  });
  deliveryTimeControl.append(
    createElement('label', { attrs: { for: 'changeover-hour' }, text: 'ساعت تغییر متن' }),
    changeoverInput
  );
  deliveryForm.append(deliveryBeforeControl, deliveryAfterControl, deliveryTimeControl);
  const deliveryActions = createElement('div', { classes: ['form-actions'] });
  const deliverySubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره متن تحویل کالا',
  });
  deliveryActions.append(deliverySubmit);
  deliveryForm.append(deliveryActions);
  deliveryGroup.append(deliveryForm);

  operationsCard.append(lunchGroup, queryGroup, deliveryGroup);

  const privateCard = createElement('div', { classes: ['card'] });
  privateCard.append(
    createElement('h4', { classes: ['section-heading__title'], text: 'تلگرام (خصوصی)' })
  );

  const privateForm = createElement('form', { classes: ['settings-form'] });
  const privateGrid = createElement('div', { classes: ['form-grid'] });

  const privateDmControl = createElement('div', { classes: ['form-control'] });
  privateDmControl.append(createElement('label', { text: 'پاسخ خودکار پیام خصوصی' }));
  const privateDmToggle = createToggle({ id: 'private-dm-toggle', checked: true });
  privateDmControl.append(privateDmToggle.wrapper);

  const privateDataSourceControl = createElement('div', { classes: ['form-control'] });
  privateDataSourceControl.append(createElement('label', { text: 'منبع داده' }));
  const privateDataSourceSelect = createElement('select', {
    attrs: { id: 'private-data-source', name: 'private-data-source' },
  });
  ['sql', 'excel'].forEach((value) => {
    const option = createElement('option', {
      attrs: { value },
      text: value === 'excel' ? 'Excel' : 'SQL Server',
    });
    privateDataSourceSelect.append(option);
  });
  privateDataSourceControl.append(privateDataSourceSelect);

  const privateExcelControl = createElement('div', { classes: ['form-control'] });
  privateExcelControl.append(
    createElement('label', { attrs: { for: 'private-excel-file' }, text: 'فایل اکسل' })
  );
  const privateExcelInput = createElement('input', {
    attrs: { type: 'text', id: 'private-excel-file', placeholder: 'inventory.xlsx' },
  });
  privateExcelControl.append(privateExcelInput);

  const privateCacheControl = createElement('div', { classes: ['form-control'] });
  privateCacheControl.append(
    createElement('label', { attrs: { for: 'private-cache-minutes' }, text: 'بازه به‌روزرسانی کش (دقیقه)' })
  );
  const privateCacheInput = createElement('input', {
    attrs: { type: 'number', id: 'private-cache-minutes', min: '1', step: '1' },
  });
  privateCacheControl.append(privateCacheInput);

  const privateWorkingStart = createElement('input', {
    attrs: { type: 'time', id: 'private-working-start' },
  });
  const privateWorkingEnd = createElement('input', {
    attrs: { type: 'time', id: 'private-working-end' },
  });
  const privateWorkingControl = createElement('div', { classes: ['form-control'] });
  privateWorkingControl.append(createElement('label', { text: 'ساعات کاری (شنبه تا چهارشنبه)' }));
  const privateWorkingRow = createElement('div', { classes: ['input-row'] });
  privateWorkingRow.append(
    createElement('span', { text: 'از' }),
    privateWorkingStart,
    createElement('span', { text: 'تا' }),
    privateWorkingEnd
  );
  privateWorkingControl.append(privateWorkingRow);

  const privateThursdayStart = createElement('input', {
    attrs: { type: 'time', id: 'private-thursday-start' },
  });
  const privateThursdayEnd = createElement('input', {
    attrs: { type: 'time', id: 'private-thursday-end' },
  });
  const privateThursdayControl = createElement('div', { classes: ['form-control'] });
  privateThursdayControl.append(createElement('label', { text: 'ساعات کاری پنج‌شنبه' }));
  const privateThursdayRow = createElement('div', { classes: ['input-row'] });
  privateThursdayRow.append(
    createElement('span', { text: 'از' }),
    privateThursdayStart,
    createElement('span', { text: 'تا' }),
    privateThursdayEnd
  );
  privateThursdayControl.append(privateThursdayRow);

  const privateFridayControl = createElement('div', { classes: ['form-control'] });
  privateFridayControl.append(createElement('label', { text: 'فعال بودن روز جمعه' }));
  const privateFridayToggle = createToggle({ id: 'private-friday-toggle', checked: false });
  privateFridayControl.append(privateFridayToggle.wrapper);

  const privateLunchStart = createElement('input', {
    attrs: { type: 'time', id: 'private-lunch-start' },
  });
  const privateLunchEnd = createElement('input', {
    attrs: { type: 'time', id: 'private-lunch-end' },
  });
  const privateLunchControl = createElement('div', { classes: ['form-control'] });
  privateLunchControl.append(createElement('label', { text: 'استراحت ناهار' }));
  const privateLunchRow = createElement('div', { classes: ['input-row'] });
  privateLunchRow.append(
    createElement('span', { text: 'از' }),
    privateLunchStart,
    createElement('span', { text: 'تا' }),
    privateLunchEnd
  );
  privateLunchControl.append(privateLunchRow);

  const privateQueryControl = createElement('div', { classes: ['form-control'] });
  privateQueryControl.append(
    createElement('label', { attrs: { for: 'private-query-limit' }, text: 'محدودیت استعلام (در ۲۴ ساعت)' })
  );
  const privateQueryInput = createElement('input', {
    attrs: { type: 'number', id: 'private-query-limit', min: '0', step: '1' },
  });
  privateQueryControl.append(privateQueryInput);

  const privateDeliveryBefore = createElement('textarea', {
    attrs: { id: 'private-delivery-before', rows: '3' },
  });
  const privateDeliveryAfter = createElement('textarea', {
    attrs: { id: 'private-delivery-after', rows: '3' },
  });
  const privateDeliveryControl = createElement('div', { classes: ['form-control'] });
  privateDeliveryControl.append(createElement('label', { text: 'متن تحویل' }));
  const privateDeliveryColumn = createElement('div', { classes: ['input-column'] });
  privateDeliveryColumn.append(
    createElement('label', { attrs: { for: 'private-delivery-before' }, text: 'قبل از ساعت تعیین‌شده' }),
    privateDeliveryBefore,
    createElement('label', { attrs: { for: 'private-delivery-after' }, text: 'بعد از ساعت تعیین‌شده' }),
    privateDeliveryAfter
  );
  privateDeliveryControl.append(privateDeliveryColumn);

  const privateChangeoverInput = createElement('input', {
    attrs: { type: 'time', id: 'private-changeover' },
  });
  const privateChangeoverControl = createElement('div', { classes: ['form-control'] });
  privateChangeoverControl.append(
    createElement('label', { attrs: { for: 'private-changeover' }, text: 'ساعت تغییر متن تحویل' }),
    privateChangeoverInput
  );

  const privateMainGroupInput = createElement('input', {
    attrs: { type: 'number', id: 'private-main-group' },
  });
  const privateNewGroupInput = createElement('input', {
    attrs: { type: 'number', id: 'private-new-group' },
  });
  const privateAdminInput = createElement('textarea', {
    attrs: { id: 'private-admin-groups', rows: '2', placeholder: 'شناسه‌ها را با ویرگول جدا کنید' },
  });
  const privateSecondaryInput = createElement('textarea', {
    attrs: { id: 'private-secondary-groups', rows: '2', placeholder: 'شناسه‌ها را با ویرگول جدا کنید' },
  });

  const privateGroupsControl = createElement('div', { classes: ['form-control'] });
  privateGroupsControl.append(createElement('label', { text: 'گروه‌ها' }));
  const privateGroupsColumn = createElement('div', { classes: ['input-column'] });
  privateGroupsColumn.append(
    createElement('label', { attrs: { for: 'private-main-group' }, text: 'گروه اصلی' }),
    privateMainGroupInput,
    createElement('label', { attrs: { for: 'private-new-group' }, text: 'گروه جست‌وجو' }),
    privateNewGroupInput,
    createElement('label', { attrs: { for: 'private-admin-groups' }, text: 'گروه‌های مدیریت' }),
    privateAdminInput,
    createElement('label', { attrs: { for: 'private-secondary-groups' }, text: 'گروه‌های فرعی' }),
    privateSecondaryInput
  );
  privateGroupsControl.append(privateGroupsColumn);

  privateGrid.append(
    privateDmControl,
    privateDataSourceControl,
    privateExcelControl,
    privateCacheControl,
    privateWorkingControl,
    privateThursdayControl,
    privateFridayControl,
    privateLunchControl,
    privateQueryControl,
    privateChangeoverControl,
    privateDeliveryControl,
    privateGroupsControl
  );

  privateForm.append(privateGrid);
  const privateActions = createElement('div', { classes: ['form-actions'] });
  const privateSubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره تنظیمات تلگرام (خصوصی)',
  });
  privateActions.append(privateSubmit);
  privateForm.append(privateActions);
  privateCard.append(privateForm);

  const platformCard = createElement('div', { classes: ['card'] });
  platformCard.append(
    createElement('h4', { classes: ['section-heading__title'], text: 'پلتفرم‌های فعال' })
  );
  const platformList = createElement('div', { classes: ['status-row'] });
  platformCard.append(platformList);

  const cacheCard = createElement('div', { classes: ['card'] });
  cacheCard.append(
    createElement('h4', { classes: ['section-heading__title'], text: 'کش' }),
    createElement('p', {
      classes: ['card__meta'],
      text: 'پاک‌سازی کش باعث دریافت مجدد داده از ربات می‌شود.',
    })
  );
  const invalidateButton = createElement('button', {
    classes: ['btn', 'btn--ghost'],
    attrs: { type: 'button' },
    text: 'پاک‌سازی کش',
  });
  cacheCard.append(invalidateButton);

  const loadingState = createLoadingState('در حال دریافت تنظیمات...');

  container.append(
    header,
    workingHoursCard,
    operationsCard,
    privateCard,
    platformCard,
    cacheCard,
    loadingState
  );

  let settings = null;

  async function loadSettings(showToast = false) {
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
  }

  function applySettings() {
    timezoneInput.value = settings.timezone ?? 'Asia/Tehran';
    dayControls.forEach((control) => {
      const current = settings.weekly.find((item) => item.day === control.day) || {
        open: null,
        close: null,
      };
      control.openInput.value = current.open ?? '';
      control.closeInput.value = current.close ?? '';
      control.closedCheckbox.checked = !current.open || !current.close;
      control.updateDisabledState();
    });

    const lunchBreak = settings.lunchBreak ?? {};
    lunchStartInput.value = lunchBreak.start ?? '';
    lunchEndInput.value = lunchBreak.end ?? '';

    if (typeof settings.queryLimit === 'number' && settings.queryLimit > 0) {
      queryLimitInput.value = settings.queryLimit;
    } else {
      queryLimitInput.value = '';
    }

    const deliveryInfo = settings.deliveryInfo ?? {};
    deliveryBeforeInput.value = deliveryInfo.before ?? '';
    deliveryAfterInput.value = deliveryInfo.after ?? '';
    changeoverInput.value = deliveryInfo.changeover ?? '';

    renderPlatformToggles(settings.platforms ?? {});

    const privateSettings = settings.privateTelegram ?? {};
    privateDmToggle.input.checked = Boolean(privateSettings.dmEnabled ?? true);
    privateDataSourceSelect.value = privateSettings.dataSource ?? 'sql';
    privateExcelInput.value = privateSettings.excelFile ?? '';
    privateCacheInput.value =
      privateSettings.cacheDurationMinutes && privateSettings.cacheDurationMinutes > 0
        ? privateSettings.cacheDurationMinutes
        : '';
    privateWorkingStart.value = privateSettings.workingHours?.start ?? '';
    privateWorkingEnd.value = privateSettings.workingHours?.end ?? '';
    privateThursdayStart.value = privateSettings.thursdayHours?.start ?? '';
    privateThursdayEnd.value = privateSettings.thursdayHours?.end ?? '';
    privateFridayToggle.input.checked = !Boolean(privateSettings.disableFriday);
    privateLunchStart.value = privateSettings.lunchBreak?.start ?? '';
    privateLunchEnd.value = privateSettings.lunchBreak?.end ?? '';
    if (typeof privateSettings.queryLimit === 'number' && privateSettings.queryLimit > 0) {
      privateQueryInput.value = privateSettings.queryLimit;
    } else {
      privateQueryInput.value = '';
    }
    privateDeliveryBefore.value = privateSettings.deliveryInfo?.before ?? '';
    privateDeliveryAfter.value = privateSettings.deliveryInfo?.after ?? '';
    privateChangeoverInput.value = privateSettings.changeoverHour ?? '';
    privateMainGroupInput.value = privateSettings.groups?.main ?? '';
    privateNewGroupInput.value = privateSettings.groups?.new ?? '';
    privateAdminInput.value = Array.isArray(privateSettings.groups?.admin)
      ? privateSettings.groups.admin.join(', ')
      : '';
    privateSecondaryInput.value = Array.isArray(privateSettings.groups?.secondary)
      ? privateSettings.groups.secondary.join(', ')
      : '';
    updatePrivateExcelVisibility();
  }

  const onWorkingHoursSubmit = async (event) => {
    event.preventDefault();
    const weekly = dayControls.map((control) => ({
      day: control.day,
      open: control.closedCheckbox.checked ? null : control.openInput.value || null,
      close: control.closedCheckbox.checked ? null : control.closeInput.value || null,
    }));
    const payload = {
      timezone: timezoneInput.value.trim() || 'Asia/Tehran',
      weekly,
    };
    try {
      workingHoursSubmit.disabled = true;
      settings = await api.updateSettings(payload);
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

  function parseGroupList(text) {
    if (!text) return [];
    return text
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => Number.parseInt(item, 10))
      .filter((val) => !Number.isNaN(val));
  }

  function updatePrivateExcelVisibility() {
    privateExcelControl.style.display = privateDataSourceSelect.value === 'excel' ? '' : 'none';
  }
  privateDataSourceSelect.addEventListener('change', updatePrivateExcelVisibility);

  const onPrivateSubmit = async (event) => {
    event.preventDefault();
    const dataSource = privateDataSourceSelect.value || 'sql';
    const cacheMinutesRaw = privateCacheInput.value.trim();
    let cacheMinutes = null;
    if (cacheMinutesRaw) {
      const parsed = Number.parseInt(cacheMinutesRaw, 10);
      if (Number.isNaN(parsed) || parsed <= 0) {
        renderToast({ message: 'بازه کش باید عددی بزرگتر از صفر باشد.', type: 'error' });
        return;
      }
      cacheMinutes = parsed;
    }

    const queryLimitRaw = privateQueryInput.value.trim();
    let privateQuery = null;
    if (queryLimitRaw) {
      const parsed = Number.parseInt(queryLimitRaw, 10);
      if (Number.isNaN(parsed) || parsed < 0) {
        renderToast({ message: 'محدودیت استعلام نامعتبر است.', type: 'error' });
        return;
      }
      privateQuery = parsed;
    }

    const payload = {
      privateTelegram: {
        dmEnabled: privateDmToggle.input.checked,
        dataSource,
        excelFile: privateExcelInput.value.trim(),
        cacheDurationMinutes: cacheMinutes,
        workingHours: {
          start: privateWorkingStart.value || null,
          end: privateWorkingEnd.value || null,
        },
        thursdayHours: {
          start: privateThursdayStart.value || null,
          end: privateThursdayEnd.value || null,
        },
        disableFriday: !privateFridayToggle.input.checked,
        lunchBreak: {
          start: privateLunchStart.value || null,
          end: privateLunchEnd.value || null,
        },
        queryLimit: privateQuery,
        deliveryInfo: {
          before: privateDeliveryBefore.value.trim(),
          after: privateDeliveryAfter.value.trim(),
        },
        changeoverHour: privateChangeoverInput.value || null,
        groups: {
          main: privateMainGroupInput.value || null,
          new: privateNewGroupInput.value || null,
          admin: parseGroupList(privateAdminInput.value),
          secondary: parseGroupList(privateSecondaryInput.value),
        },
      },
    };

    try {
      privateSubmit.disabled = true;
      settings = await api.updateSettings(payload);
      applySettings();
      renderToast({ message: 'تنظیمات تلگرام (خصوصی) ذخیره شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      privateSubmit.disabled = false;
    }
  };
  privateForm.addEventListener('submit', onPrivateSubmit);

  function renderPlatformToggles(platforms) {
    platformList.innerHTML = '';
    const telegramToggle = createToggle({
      id: 'telegram-toggle',
      checked: platforms.telegram ?? true,
      label: 'تلگرام',
      onChange: (checked) => handlePlatformChange('telegram', checked, telegramToggle.input),
    });
    const whatsappToggle = createToggle({
      id: 'whatsapp-toggle',
      checked: platforms.whatsapp ?? true,
      label: 'واتساپ',
      onChange: (checked) => handlePlatformChange('whatsapp', checked, whatsappToggle.input),
    });
    const privateToggle = createToggle({
      id: 'private-telegram-toggle',
      checked: platforms.telegram_private ?? true,
      label: 'تلگرام (خصوصی)',
      onChange: (checked) => handlePlatformChange('telegram_private', checked, privateToggle.input),
    });

    const telegramRow = createElement('div', { classes: ['status-row__item'] });
    telegramRow.append(createElement('span', { text: 'تلگرام' }), telegramToggle.wrapper);
    const whatsappRow = createElement('div', { classes: ['status-row__item'] });
    whatsappRow.append(createElement('span', { text: 'واتساپ' }), whatsappToggle.wrapper);
    const privateRow = createElement('div', { classes: ['status-row__item'] });
    privateRow.append(createElement('span', { text: 'تلگرام (خصوصی)' }), privateToggle.wrapper);

    platformList.append(telegramRow, whatsappRow, privateRow);
  }

  async function handlePlatformChange(platform, checked, inputEl) {
    try {
      inputEl.disabled = true;
      settings = await api.updateSettings({
        platforms: {
          ...(settings?.platforms ?? {}),
          [platform]: checked,
        },
      });
      window.APP_CONFIG = {
        ...(window.APP_CONFIG ?? {}),
        [`${platform.toUpperCase()}_ENABLED`]: checked,
      };
      const platformLabels = {
        telegram: 'تلگرام',
        whatsapp: 'واتساپ',
        telegram_private: 'تلگرام (خصوصی)',
      };
      const platformLabel = platformLabels[platform] ?? platform;
      renderToast({ message: `پلتفرم ${platformLabel} ${checked ? 'فعال' : 'غیرفعال'} شد.` });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
      inputEl.checked = !checked;
    } finally {
      inputEl.disabled = false;
    }
  }

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

  await loadSettings();

  return {
    async refresh() {
      await loadSettings(true);
    },
    destroy() {
      workingHoursForm.removeEventListener('submit', onWorkingHoursSubmit);
      lunchForm.removeEventListener('submit', onLunchSubmit);
      queryForm.removeEventListener('submit', onQuerySubmit);
      deliveryForm.removeEventListener('submit', onDeliverySubmit);
      privateForm.removeEventListener('submit', onPrivateSubmit);
      privateDataSourceSelect.removeEventListener('change', updatePrivateExcelVisibility);
      invalidateButton.removeEventListener('click', onInvalidateClick);
      dayControls.forEach((control) => control.dispose?.());
    },
  };
}
