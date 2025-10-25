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
      checked: platforms.privateTelegram ?? true,
      label: 'تلگرام خصوصی',
      onChange: (checked) =>
        handlePlatformChange('privateTelegram', checked, privateToggle.input),
    });

    const telegramRow = createElement('div', { classes: ['status-row__item'] });
    telegramRow.append(createElement('span', { text: 'تلگرام' }), telegramToggle.wrapper);
    const privateRow = createElement('div', { classes: ['status-row__item'] });
    privateRow.append(createElement('span', { text: 'تلگرام خصوصی' }), privateToggle.wrapper);
    const whatsappRow = createElement('div', { classes: ['status-row__item'] });
    whatsappRow.append(createElement('span', { text: 'واتساپ' }), whatsappToggle.wrapper);

    platformList.append(telegramRow, privateRow, whatsappRow);
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
      const platformLabels = {
        telegram: 'تلگرام',
        whatsapp: 'واتساپ',
        privateTelegram: 'تلگرام خصوصی',
      };
      const platformLabel = platformLabels[platform] ?? platform;
      renderToast({
        message: `پلتفرم ${platformLabel} ${checked ? 'فعال' : 'غیرفعال'} شد.`,
      });
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
      invalidateButton.removeEventListener('click', onInvalidateClick);
      dayControls.forEach((control) => control.dispose?.());
    },
  };
}
