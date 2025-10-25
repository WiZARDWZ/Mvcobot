import { api } from '../api.js';
import {
  createElement,
  createLoadingState,
  createToggle,
  renderToast,
} from './components.js';

function parseInteger(value, label) {
  const trimmed = String(value ?? '').trim();
  if (!trimmed) {
    throw new Error(`${label} را وارد کنید.`);
  }
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed)) {
    throw new Error(`${label} باید عددی باشد.`);
  }
  return parsed;
}

function parseOptionalInteger(value) {
  const trimmed = String(value ?? '').trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed)) {
    throw new Error('مقدار عددی نامعتبر است.');
  }
  return parsed;
}

function parseIdList(text) {
  const tokens = String(text ?? '')
    .split(/[\s,;\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const result = tokens.map((token) => {
    const parsed = Number(token);
    if (Number.isNaN(parsed)) {
      throw new Error('شناسه باید عددی باشد.');
    }
    return parsed;
  });
  return result;
}

export async function mount(container) {
  const disposables = [];
  let settings = null;

  const header = createElement('div', { classes: ['section-heading'] });
  header.append(
    createElement('h3', { classes: ['section-heading__title'], text: 'تلگرام خصوصی' }),
    createElement('p', {
      classes: ['section-heading__subtitle'],
      text: 'پاسخ‌گویی خودکار تلگرام خصوصی را از این بخش مدیریت کنید.',
    })
  );
  container.append(header);

  const layout = createElement('div', { classes: ['page-layout'] });
  container.append(layout);

  const loading = createLoadingState('در حال دریافت تنظیمات تلگرام خصوصی...');
  container.append(loading);

  try {
    settings = await api.getPrivateTelegramSettings();
  } catch (error) {
    loading.replaceWith(
      createElement('div', {
        classes: ['empty-state'],
        text: `بارگذاری تنظیمات تلگرام خصوصی با خطا مواجه شد: ${error.message}`,
      })
    );
    return {
      async refresh() {},
      destroy() {},
    };
  }

  loading.remove();

  // ─── General settings card ───
  let enabledToggle;
  let dmToggle;
  let apiIdInput;
  let apiHashInput;
  let phoneInput;
  let dataSourceSelect;
  let excelFileInput;
  let cacheDurationInput;

  const generalCard = createElement('div', { classes: ['card'] });
  generalCard.append(
    createElement('h4', { classes: ['section-heading__title'], text: 'تنظیمات کلی' })
  );
  const generalForm = createElement('form', { classes: ['settings-form'] });

  const toggleRow = createElement('div', { classes: ['status-row'] });
  enabledToggle = createToggle({ id: 'private-enabled', checked: false, label: 'فعال بودن ربات' });
  dmToggle = createToggle({ id: 'private-dm', checked: false, label: 'پیام خصوصی' });
  const enabledRow = createElement('div', { classes: ['status-row__item'] });
  enabledRow.append(createElement('span', { text: 'فعال بودن ربات' }), enabledToggle.wrapper);
  const dmRow = createElement('div', { classes: ['status-row__item'] });
  dmRow.append(createElement('span', { text: 'پاسخ پیام خصوصی' }), dmToggle.wrapper);
  toggleRow.append(enabledRow, dmRow);
  generalForm.append(toggleRow);

  const generalGrid = createElement('div', { classes: ['form-grid'] });

  const apiIdControl = createElement('div', { classes: ['form-control'] });
  apiIdControl.append(
    createElement('label', { attrs: { for: 'private-api-id' }, text: 'API ID' })
  );
  apiIdInput = createElement('input', {
    attrs: { type: 'number', id: 'private-api-id', name: 'apiId', required: true, min: '1' },
  });
  apiIdControl.append(apiIdInput);

  const apiHashControl = createElement('div', { classes: ['form-control'] });
  apiHashControl.append(
    createElement('label', { attrs: { for: 'private-api-hash' }, text: 'API Hash' })
  );
  apiHashInput = createElement('input', {
    attrs: { type: 'text', id: 'private-api-hash', name: 'apiHash', required: true },
  });
  apiHashControl.append(apiHashInput);

  const phoneControl = createElement('div', { classes: ['form-control'] });
  phoneControl.append(
    createElement('label', { attrs: { for: 'private-phone-number' }, text: 'شماره تلفن' })
  );
  phoneInput = createElement('input', {
    attrs: { type: 'text', id: 'private-phone-number', name: 'phoneNumber', required: true },
  });
  phoneControl.append(phoneInput);

  const dataSourceControl = createElement('div', { classes: ['form-control'] });
  dataSourceControl.append(
    createElement('label', { attrs: { for: 'private-data-source' }, text: 'منبع داده' })
  );
  dataSourceSelect = createElement('select', {
    attrs: { id: 'private-data-source', name: 'dataSource' },
  });
  dataSourceSelect.append(
    createElement('option', { attrs: { value: 'sql' }, text: 'SQL' }),
    createElement('option', { attrs: { value: 'excel' }, text: 'Excel' })
  );
  dataSourceControl.append(dataSourceSelect);

  const excelControl = createElement('div', { classes: ['form-control'] });
  excelControl.append(
    createElement('label', { attrs: { for: 'private-excel-file' }, text: 'فایل اکسل' })
  );
  excelFileInput = createElement('input', {
    attrs: { type: 'text', id: 'private-excel-file', name: 'excelFile' },
  });
  excelControl.append(excelFileInput);

  const cacheControl = createElement('div', { classes: ['form-control'] });
  cacheControl.append(
    createElement('label', {
      attrs: { for: 'private-cache-duration' },
      text: 'مدت کش (دقیقه)',
    })
  );
  cacheDurationInput = createElement('input', {
    attrs: { type: 'number', id: 'private-cache-duration', name: 'cacheDuration', min: '0' },
  });
  cacheControl.append(cacheDurationInput);

  generalGrid.append(apiIdControl, apiHashControl, phoneControl, dataSourceControl, excelControl, cacheControl);
  generalForm.append(generalGrid);

  const generalActions = createElement('div', { classes: ['form-actions'] });
  const generalSubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره تنظیمات کلی',
  });
  generalActions.append(generalSubmit);
  generalForm.append(generalActions);
  generalCard.append(generalForm);
  layout.append(generalCard);

  const updateExcelVisibility = () => {
    const value = dataSourceSelect.value;
    excelControl.hidden = value !== 'excel';
  };
  dataSourceSelect.addEventListener('change', updateExcelVisibility);
  disposables.push(() => dataSourceSelect.removeEventListener('change', updateExcelVisibility));

  const handleGeneralSubmit = async (event) => {
    event.preventDefault();
    let apiId;
    let cacheMinutes = 0;
    try {
      apiId = parseInteger(apiIdInput.value, 'API ID');
      const cacheValue = cacheDurationInput.value;
      if (cacheValue !== '') {
        const parsedCache = Number(cacheValue);
        if (Number.isNaN(parsedCache) || parsedCache < 0) {
          throw new Error('مدت کش باید عددی و مثبت باشد.');
        }
        cacheMinutes = parsedCache;
      }
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
      return;
    }

    const payload = {
      enabled: enabledToggle.input.checked,
      dmEnabled: dmToggle.input.checked,
      apiId,
      apiHash: apiHashInput.value.trim(),
      phoneNumber: phoneInput.value.trim(),
      dataSource: dataSourceSelect.value,
      excelFile: excelFileInput.value.trim(),
      cacheDurationMinutes: cacheMinutes,
    };

    try {
      generalSubmit.disabled = true;
      const updated = await api.updatePrivateTelegramSettings(payload);
      settings = updated;
      applySettings();
      renderToast({ message: 'تنظیمات کلی ذخیره شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      generalSubmit.disabled = false;
    }
  };
  generalForm.addEventListener('submit', handleGeneralSubmit);
  disposables.push(() => generalForm.removeEventListener('submit', handleGeneralSubmit));

  // ─── Scheduling and messaging card ───
  let workingStartInput;
  let workingEndInput;
  let thursdayStartInput;
  let thursdayEndInput;
  let disableFridayToggle;
  let lunchStartInput;
  let lunchEndInput;
  let changeoverInput;
  let queryLimitInput;
  let deliveryBeforeInput;
  let deliveryAfterInput;

  const scheduleCard = createElement('div', { classes: ['card'] });
  scheduleCard.append(
    createElement('h4', { classes: ['section-heading__title'], text: 'زمان‌بندی و پیام‌ها' })
  );
  const scheduleForm = createElement('form', { classes: ['settings-form'] });

  const workingGrid = createElement('div', { classes: ['form-grid'] });
  const workingControl = createElement('div', { classes: ['form-control'] });
  workingControl.append(createElement('label', { text: 'ساعات کاری شنبه تا چهارشنبه' }));
  const workingRow = createElement('div', { classes: ['working-hours__times'] });
  workingStartInput = createElement('input', { attrs: { type: 'time', id: 'private-working-start' } });
  workingEndInput = createElement('input', { attrs: { type: 'time', id: 'private-working-end' } });
  workingRow.append(
    createElement('span', { text: 'از' }),
    workingStartInput,
    createElement('span', { text: 'تا' }),
    workingEndInput
  );
  workingControl.append(workingRow);

  const thursdayControl = createElement('div', { classes: ['form-control'] });
  thursdayControl.append(createElement('label', { text: 'ساعات کاری پنج‌شنبه' }));
  const thursdayRow = createElement('div', { classes: ['working-hours__times'] });
  thursdayStartInput = createElement('input', { attrs: { type: 'time', id: 'private-thursday-start' } });
  thursdayEndInput = createElement('input', { attrs: { type: 'time', id: 'private-thursday-end' } });
  thursdayRow.append(
    createElement('span', { text: 'از' }),
    thursdayStartInput,
    createElement('span', { text: 'تا' }),
    thursdayEndInput
  );
  thursdayControl.append(thursdayRow);

  workingGrid.append(workingControl, thursdayControl);
  scheduleForm.append(workingGrid);

  const fridayRow = createElement('div', { classes: ['status-row'] });
  disableFridayToggle = createToggle({ id: 'private-disable-friday', checked: false, label: 'وضعیت جمعه' });
  const fridayItem = createElement('div', { classes: ['status-row__item'] });
  fridayItem.append(createElement('span', { text: 'تعطیلی روز جمعه' }), disableFridayToggle.wrapper);
  fridayRow.append(fridayItem);
  scheduleForm.append(fridayRow);

  const lunchGrid = createElement('div', { classes: ['form-grid'] });
  const lunchStartControl = createElement('div', { classes: ['form-control'] });
  lunchStartControl.append(
    createElement('label', { attrs: { for: 'private-lunch-start' }, text: 'شروع ناهار' })
  );
  lunchStartInput = createElement('input', { attrs: { type: 'time', id: 'private-lunch-start' } });
  lunchStartControl.append(lunchStartInput);

  const lunchEndControl = createElement('div', { classes: ['form-control'] });
  lunchEndControl.append(
    createElement('label', { attrs: { for: 'private-lunch-end' }, text: 'پایان ناهار' })
  );
  lunchEndInput = createElement('input', { attrs: { type: 'time', id: 'private-lunch-end' } });
  lunchEndControl.append(lunchEndInput);

  lunchGrid.append(lunchStartControl, lunchEndControl);
  scheduleForm.append(lunchGrid);

  const miscGrid = createElement('div', { classes: ['form-grid'] });
  const changeoverControl = createElement('div', { classes: ['form-control'] });
  changeoverControl.append(
    createElement('label', { attrs: { for: 'private-changeover' }, text: 'ساعت تغییر متن تحویل' })
  );
  changeoverInput = createElement('input', { attrs: { type: 'time', id: 'private-changeover' } });
  changeoverControl.append(changeoverInput);

  const queryControl = createElement('div', { classes: ['form-control'] });
  queryControl.append(
    createElement('label', { attrs: { for: 'private-query-limit' }, text: 'محدودیت استعلام (۲۴ ساعته)' })
  );
  queryLimitInput = createElement('input', {
    attrs: { type: 'number', id: 'private-query-limit', min: '0', inputmode: 'numeric' },
  });
  queryControl.append(
    queryLimitInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'برای حذف محدودیت مقدار را خالی بگذارید.',
    })
  );

  miscGrid.append(changeoverControl, queryControl);
  scheduleForm.append(miscGrid);

  const deliveryGroup = createElement('div', { classes: ['settings-card__group'] });
  deliveryGroup.append(
    createElement('h5', { classes: ['settings-card__subtitle'], text: 'متن تحویل کالا' })
  );
  const deliveryGrid = createElement('div', { classes: ['form-grid'] });
  const beforeControl = createElement('div', { classes: ['form-control'] });
  beforeControl.append(
    createElement('label', { attrs: { for: 'private-delivery-before' }, text: 'قبل از ساعت تغییر' })
  );
  deliveryBeforeInput = createElement('textarea', {
    attrs: { id: 'private-delivery-before', rows: '3' },
  });
  beforeControl.append(deliveryBeforeInput);

  const afterControl = createElement('div', { classes: ['form-control'] });
  afterControl.append(
    createElement('label', { attrs: { for: 'private-delivery-after' }, text: 'بعد از ساعت تغییر' })
  );
  deliveryAfterInput = createElement('textarea', {
    attrs: { id: 'private-delivery-after', rows: '3' },
  });
  afterControl.append(deliveryAfterInput);

  deliveryGrid.append(beforeControl, afterControl);
  deliveryGroup.append(deliveryGrid);
  scheduleForm.append(deliveryGroup);

  const scheduleActions = createElement('div', { classes: ['form-actions'] });
  const scheduleSubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره زمان‌بندی و پیام‌ها',
  });
  scheduleActions.append(scheduleSubmit);
  scheduleForm.append(scheduleActions);
  scheduleCard.append(scheduleForm);
  layout.append(scheduleCard);

  const handleScheduleSubmit = async (event) => {
    event.preventDefault();
    let queryLimit = null;
    try {
      queryLimit = parseOptionalInteger(queryLimitInput.value);
      if (queryLimit !== null && queryLimit < 0) {
        throw new Error('محدودیت استعلام نمی‌تواند منفی باشد.');
      }
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
      return;
    }

    const payload = {
      workingHours: {
        start: workingStartInput.value || '',
        end: workingEndInput.value || '',
      },
      thursdayHours: {
        start: thursdayStartInput.value || '',
        end: thursdayEndInput.value || '',
      },
      disableFriday: disableFridayToggle.input.checked,
      lunchBreak: {
        start: lunchStartInput.value || '',
        end: lunchEndInput.value || '',
      },
      changeoverHour: changeoverInput.value || '',
      queryLimit,
      deliveryInfo: {
        before15: deliveryBeforeInput.value.trim(),
        after15: deliveryAfterInput.value.trim(),
      },
    };

    try {
      scheduleSubmit.disabled = true;
      const updated = await api.updatePrivateTelegramSettings(payload);
      settings = updated;
      applySettings();
      renderToast({ message: 'زمان‌بندی ذخیره شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      scheduleSubmit.disabled = false;
    }
  };
  scheduleForm.addEventListener('submit', handleScheduleSubmit);
  disposables.push(() => scheduleForm.removeEventListener('submit', handleScheduleSubmit));

  // ─── Groups and blacklist card ───
  let mainGroupInput;
  let newGroupInput;
  let adminGroupsInput;
  let secondaryGroupsInput;
  let blacklistInput;

  const groupsCard = createElement('div', { classes: ['card'] });
  groupsCard.append(
    createElement('h4', { classes: ['section-heading__title'], text: 'گروه‌ها و لیست سیاه' })
  );
  const groupsForm = createElement('form', { classes: ['settings-form'] });

  const groupsGrid = createElement('div', { classes: ['form-grid'] });
  const mainGroupControl = createElement('div', { classes: ['form-control'] });
  mainGroupControl.append(
    createElement('label', { attrs: { for: 'private-main-group' }, text: 'گروه اصلی' })
  );
  mainGroupInput = createElement('input', {
    attrs: { type: 'text', id: 'private-main-group', required: true },
  });
  mainGroupControl.append(mainGroupInput);

  const newGroupControl = createElement('div', { classes: ['form-control'] });
  newGroupControl.append(
    createElement('label', { attrs: { for: 'private-new-group' }, text: 'گروه تازه‌وارد' })
  );
  newGroupInput = createElement('input', {
    attrs: { type: 'text', id: 'private-new-group', required: true },
  });
  newGroupControl.append(newGroupInput);

  groupsGrid.append(mainGroupControl, newGroupControl);
  groupsForm.append(groupsGrid);

  const adminControl = createElement('div', { classes: ['form-control'] });
  adminControl.append(
    createElement('label', { attrs: { for: 'private-admin-groups' }, text: 'گروه‌های مدیریت (هر خط یک مورد)' })
  );
  adminGroupsInput = createElement('textarea', {
    attrs: { id: 'private-admin-groups', rows: '3', placeholder: '-1001234567890' },
  });
  adminControl.append(adminGroupsInput);

  const secondaryControl = createElement('div', { classes: ['form-control'] });
  secondaryControl.append(
    createElement('label', { attrs: { for: 'private-secondary-groups' }, text: 'گروه‌های فرعی (اختیاری)' })
  );
  secondaryGroupsInput = createElement('textarea', {
    attrs: { id: 'private-secondary-groups', rows: '3', placeholder: '-100...' },
  });
  secondaryControl.append(secondaryGroupsInput);

  const blacklistControl = createElement('div', { classes: ['form-control'] });
  blacklistControl.append(
    createElement('label', { attrs: { for: 'private-blacklist' }, text: 'لیست سیاه (هر خط یک شناسه)' })
  );
  blacklistInput = createElement('textarea', {
    attrs: { id: 'private-blacklist', rows: '4', placeholder: '437739989' },
  });
  blacklistControl.append(blacklistInput);

  groupsForm.append(adminControl, secondaryControl, blacklistControl);

  const groupsActions = createElement('div', { classes: ['form-actions'] });
  const groupsSubmit = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره گروه‌ها و لیست سیاه',
  });
  groupsActions.append(groupsSubmit);
  groupsForm.append(groupsActions);
  groupsCard.append(groupsForm);
  layout.append(groupsCard);

  const handleGroupsSubmit = async (event) => {
    event.preventDefault();
    let mainGroupId;
    let newGroupId;
    let adminIds;
    let secondaryIds;
    let blacklistIds;
    try {
      mainGroupId = parseInteger(mainGroupInput.value, 'گروه اصلی');
      newGroupId = parseInteger(newGroupInput.value, 'گروه تازه‌وارد');
      adminIds = parseIdList(adminGroupsInput.value);
      secondaryIds = parseIdList(secondaryGroupsInput.value);
      blacklistIds = parseIdList(blacklistInput.value);
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
      return;
    }

    const payload = {
      mainGroupId,
      newGroupId,
      adminGroupIds: adminIds,
      secondaryGroupIds: secondaryIds,
      blacklist: blacklistIds,
    };

    try {
      groupsSubmit.disabled = true;
      const updated = await api.updatePrivateTelegramSettings(payload);
      settings = updated;
      applySettings();
      renderToast({ message: 'گروه‌ها و لیست سیاه ذخیره شد.' });
    } catch (error) {
      renderToast({ message: error.message, type: 'error' });
    } finally {
      groupsSubmit.disabled = false;
    }
  };
  groupsForm.addEventListener('submit', handleGroupsSubmit);
  disposables.push(() => groupsForm.removeEventListener('submit', handleGroupsSubmit));

  function applySettings() {
    if (!settings) return;
    enabledToggle.input.checked = Boolean(settings.enabled);
    dmToggle.input.checked = Boolean(settings.dmEnabled);
    apiIdInput.value = settings.apiId ?? '';
    apiHashInput.value = settings.apiHash ?? '';
    phoneInput.value = settings.phoneNumber ?? '';
    dataSourceSelect.value = settings.dataSource ?? 'sql';
    excelFileInput.value = settings.excelFile ?? '';
    cacheDurationInput.value = settings.cacheDurationMinutes ?? '';
    updateExcelVisibility();

    workingStartInput.value = settings.workingHours?.start ?? '';
    workingEndInput.value = settings.workingHours?.end ?? '';
    thursdayStartInput.value = settings.thursdayHours?.start ?? '';
    thursdayEndInput.value = settings.thursdayHours?.end ?? '';
    disableFridayToggle.input.checked = Boolean(settings.disableFriday);
    lunchStartInput.value = settings.lunchBreak?.start ?? '';
    lunchEndInput.value = settings.lunchBreak?.end ?? '';
    changeoverInput.value = settings.changeoverHour ?? '';
    queryLimitInput.value = settings.queryLimit ?? '';
    deliveryBeforeInput.value = settings.deliveryInfo?.before15 ?? '';
    deliveryAfterInput.value = settings.deliveryInfo?.after15 ?? '';

    mainGroupInput.value = settings.mainGroupId ?? '';
    newGroupInput.value = settings.newGroupId ?? '';
    adminGroupsInput.value = (settings.adminGroupIds || []).join('\n');
    secondaryGroupsInput.value = (settings.secondaryGroupIds || []).join('\n');
    blacklistInput.value = (settings.blacklist || []).join('\n');
  }

  applySettings();

  return {
    async refresh() {
      try {
        const fresh = await api.getPrivateTelegramSettings();
        settings = fresh;
        applySettings();
      } catch (error) {
        renderToast({ message: error.message, type: 'error' });
      }
    },
    destroy() {
      disposables.forEach((fn) => fn());
    },
  };
}
