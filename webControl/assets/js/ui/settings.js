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
  { day: 0, label: 'یکشنبه' },
  { day: 1, label: 'دوشنبه' },
  { day: 2, label: 'سه‌شنبه' },
  { day: 3, label: 'چهارشنبه' },
  { day: 4, label: 'پنجشنبه' },
  { day: 5, label: 'جمعه' },
  { day: 6, label: 'شنبه' },
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

  container.append(header, workingHoursCard, platformCard, cacheCard, loadingState);

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

    const telegramRow = createElement('div', { classes: ['status-row__item'] });
    telegramRow.append(createElement('span', { text: 'تلگرام' }), telegramToggle.wrapper);
    const whatsappRow = createElement('div', { classes: ['status-row__item'] });
    whatsappRow.append(createElement('span', { text: 'واتساپ' }), whatsappToggle.wrapper);

    platformList.append(telegramRow, whatsappRow);
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
      renderToast({ message: `پلتفرم ${platform === 'telegram' ? 'تلگرام' : 'واتساپ'} ${checked ? 'فعال' : 'غیرفعال'} شد.` });
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
      invalidateButton.removeEventListener('click', onInvalidateClick);
      dayControls.forEach((control) => control.dispose?.());
    },
  };
}
