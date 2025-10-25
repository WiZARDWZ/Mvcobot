/**
 * Private DM bot settings view.
 */
import { api } from '../api.js';
import {
  createBadge,
  createElement,
  createLoadingState,
  createToggle,
  renderToast,
} from './components.js';

function formatStatus(value) {
  if (!value) return 'نامشخص';
  const normalized = String(value).toLowerCase();
  if (normalized.includes('run')) return 'فعال';
  if (normalized.includes('disable')) return 'غیرفعال';
  if (normalized.includes('error')) return 'خطا';
  return value;
}

function statusVariant(value) {
  if (!value) return 'default';
  const normalized = String(value).toLowerCase();
  if (normalized.includes('run')) return 'success';
  if (normalized.includes('error')) return 'danger';
  return 'default';
}

export async function mount(container) {
  const heading = createElement('div', { classes: ['section-heading'] });
  heading.append(
    createElement('h3', { classes: ['section-heading__title'], text: 'ربات پیام خصوصی (DM)' }),
    createElement('p', {
      classes: ['section-heading__subtitle'],
      text: 'توکن، ساعات کاری و کانال لاگ ربات پیام خصوصی را مدیریت کنید.',
    })
  );

  const statusWrapper = createElement('div', { classes: ['dm-status'] });
  const statusLabel = createElement('span', { classes: ['dm-status__label'], text: 'وضعیت سرویس:' });
  let statusBadge = createBadge('در حال بررسی...');
  statusWrapper.append(statusLabel, statusBadge);
  heading.append(statusWrapper);

  const card = createElement('div', { classes: ['card'] });
  const form = createElement('form', { classes: ['settings-form'] });

  const enabledControl = createElement('div', { classes: ['form-control'] });
  enabledControl.append(createElement('label', { attrs: { for: 'dm-enabled' }, text: 'فعال بودن ربات DM' }));
  const enabledToggle = createToggle({ id: 'dm-enabled', label: 'فعال بودن ربات DM' });
  enabledControl.append(enabledToggle.wrapper);

  const tokenControl = createElement('div', { classes: ['form-control'] });
  const tokenInput = createElement('input', {
    attrs: { type: 'text', id: 'dm-token', name: 'token', dir: 'ltr', autocomplete: 'off' },
  });
  tokenControl.append(
    createElement('label', { attrs: { for: 'dm-token' }, text: 'توکن ربات DM' }),
    tokenInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'توکن باید از BotFather دریافت شود. مقادیر خالی باعث غیرفعال شدن ربات می‌شود.',
    })
  );

  const channelControl = createElement('div', { classes: ['form-control'] });
  const channelInput = createElement('input', {
    attrs: { type: 'text', id: 'dm-channel', name: 'channelId', dir: 'ltr', placeholder: '-1001234567890' },
  });
  channelControl.append(
    createElement('label', { attrs: { for: 'dm-channel' }, text: 'کانال لاگ خصوصی' }),
    channelInput,
    createElement('p', {
      classes: ['form-control__hint'],
      text: 'شناسه یا یوزرنیم کانال خصوصی برای ارسال لاگ پیام‌ها.',
    })
  );

  const hoursGroup = createElement('div', { classes: ['form-grid'] });
  const startControl = createElement('div', { classes: ['form-control'] });
  const startInput = createElement('input', {
    attrs: { type: 'time', id: 'dm-hours-start', name: 'workHoursStart' },
  });
  startControl.append(
    createElement('label', { attrs: { for: 'dm-hours-start' }, text: 'شروع ساعات کاری' }),
    startInput
  );
  const endControl = createElement('div', { classes: ['form-control'] });
  const endInput = createElement('input', {
    attrs: { type: 'time', id: 'dm-hours-end', name: 'workHoursEnd' },
  });
  endControl.append(
    createElement('label', { attrs: { for: 'dm-hours-end' }, text: 'پایان ساعات کاری' }),
    endInput
  );
  hoursGroup.append(startControl, endControl);

  const rateControl = createElement('div', { classes: ['form-control'] });
  const rateInput = createElement('input', {
    attrs: { type: 'text', id: 'dm-rate', name: 'rateLimit', placeholder: '20/min', dir: 'ltr' },
  });
  rateControl.append(
    createElement('label', { attrs: { for: 'dm-rate' }, text: 'Rate Limit (اختیاری)' }),
    rateInput
  );

  const whitelistControl = createElement('div', { classes: ['form-control'] });
  const whitelistInput = createElement('textarea', {
    attrs: { id: 'dm-whitelist', name: 'whitelist', rows: '2', dir: 'ltr', placeholder: '12345,67890' },
  });
  whitelistControl.append(
    createElement('label', { attrs: { for: 'dm-whitelist' }, text: 'لیست سفید کاربران (شناسه‌ها با کاما جدا شوند)' }),
    whitelistInput
  );

  const actions = createElement('div', { classes: ['form-actions'] });
  const submitButton = createElement('button', {
    classes: ['btn', 'btn--primary'],
    attrs: { type: 'submit' },
    text: 'ذخیره تنظیمات DM',
  });
  const testButton = createElement('button', {
    classes: ['btn', 'btn--ghost'],
    attrs: { type: 'button' },
    text: 'ارسال پیام تست',
  });
  actions.append(submitButton, testButton);

  form.append(
    enabledControl,
    tokenControl,
    channelControl,
    hoursGroup,
    rateControl,
    whitelistControl,
    actions
  );
  card.append(form);

  const loadingState = createLoadingState('در حال دریافت تنظیمات DM Bot...');
  card.append(loadingState);

  container.append(heading, card);

  let destroyed = false;

  const updateStatus = (status) => {
    const variant = statusVariant(status);
    const label = formatStatus(status);
    const newBadge = createBadge(label, variant);
    statusBadge.replaceWith(newBadge);
    statusBadge = newBadge;
  };

  const populate = (data) => {
    const settings = data?.settings ?? {};
    enabledToggle.input.checked = Boolean(settings.enabled);
    tokenInput.value = settings.token ?? '';
    channelInput.value = settings.channelId ?? '';
    startInput.value = settings.workHoursStart ?? '';
    endInput.value = settings.workHoursEnd ?? '';
    rateInput.value = settings.rateLimit ?? '';
    whitelistInput.value = (settings.whitelist ?? '')
      .split(',')
      .filter(Boolean)
      .join('\n');
    updateStatus(data?.status ?? '');
  };

  async function load() {
    loadingState.hidden = false;
    try {
      const data = await api.getDMBotSettings();
      if (destroyed) return;
      populate(data);
    } catch (error) {
      console.error('Failed to load DM settings', error);
      renderToast({ message: 'دریافت تنظیمات DM Bot با خطا مواجه شد.', type: 'error' });
    } finally {
      loadingState.hidden = true;
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    submitButton.disabled = true;
    try {
      const payload = {
        enabled: enabledToggle.input.checked,
        token: tokenInput.value.trim(),
        channelId: channelInput.value.trim(),
        workHoursStart: startInput.value || '',
        workHoursEnd: endInput.value || '',
        rateLimit: rateInput.value.trim(),
        whitelist: whitelistInput.value
          .split(/[\n,]+/)
          .map((item) => item.trim())
          .filter(Boolean)
          .join(','),
      };
      const result = await api.updateDMBotSettings(payload);
      populate(result);
      renderToast({ message: 'تنظیمات DM Bot با موفقیت ذخیره شد.' });
    } catch (error) {
      console.error('Failed to update DM settings', error);
      renderToast({ message: error?.message || 'خطا در ذخیره تنظیمات DM', type: 'error' });
    } finally {
      submitButton.disabled = false;
    }
  }

  async function handleTest() {
    testButton.disabled = true;
    try {
      await api.testDMBot();
      renderToast({ message: 'پیام تست با موفقیت ارسال شد.' });
    } catch (error) {
      console.error('Failed to send DM test message', error);
      renderToast({ message: error?.message || 'ارسال پیام تست ممکن نشد.', type: 'error' });
    } finally {
      testButton.disabled = false;
    }
  }

  form.addEventListener('submit', handleSubmit);
  testButton.addEventListener('click', handleTest);

  await load();

  return {
    async refresh() {
      await load();
    },
    destroy() {
      destroyed = true;
      form.removeEventListener('submit', handleSubmit);
      testButton.removeEventListener('click', handleTest);
    },
  };
}
