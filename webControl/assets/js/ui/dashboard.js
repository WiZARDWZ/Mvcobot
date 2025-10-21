/**
 * Dashboard tab module.
 */
import { api } from '../api.js';
import {
  clearChildren,
  createBadge,
  createElement,
  createLoadingState,
  createToggle,
  formatDateTime,
  formatRelativeTime,
  renderToast,
  renderWorkingHoursList,
} from './components.js';

let chartInstance = null;

function destroyChart() {
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }
}

function renderStatsCard({ label, value, meta }) {
  const card = createElement('div', { classes: ['card'] });
  card.append(
    createElement('p', { classes: ['card__label'], text: label }),
    createElement('p', { classes: ['card__value'], text: value.toLocaleString('fa-IR') })
  );
  if (meta) {
    card.append(createElement('p', { classes: ['card__meta'], text: meta }));
  }
  return card;
}

function buildChart(container, metrics) {
  destroyChart();
  if (!window.Chart) {
    container.appendChild(
      createElement('p', {
        classes: ['card__meta'],
        text: 'امکان نمایش نمودار وجود ندارد. اسکریپت Chart.js در دسترس نیست.',
      })
    );
    return;
  }

  const canvas = createElement('canvas');
  container.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  const labels = metrics.monthly.map((item) => item.month);
  const telegramData = metrics.monthly.map((item) => item.telegram);
  const whatsappData = metrics.monthly.map((item) => item.whatsapp);
  const privateTelegramData = metrics.monthly.map((item) => item.privateTelegram ?? 0);

  chartInstance = new window.Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'تلگرام',
          data: telegramData,
          backgroundColor: 'rgba(88, 101, 242, 0.7)',
          borderRadius: 6,
        },
        {
          label: 'تلگرام (شخصی)',
          data: privateTelegramData,
          backgroundColor: 'rgba(236, 72, 153, 0.6)',
          borderRadius: 6,
        },
        {
          label: 'واتساپ',
          data: whatsappData,
          backgroundColor: 'rgba(34, 197, 94, 0.6)',
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          ticks: {
            callback(value) {
              return Number(value).toLocaleString('fa-IR');
            },
          },
        },
      },
      plugins: {
        legend: {
          position: 'bottom',
        },
      },
    },
  });
}

export async function mount(container) {
  const header = createElement('div', { classes: ['section-heading'] });
  header.append(
    createElement('h3', { classes: ['section-heading__title'], text: 'نمای کلی ربات' })
  );

  const statsGrid = createElement('div', { classes: ['grid', 'grid--stats'] });
  const chartCard = createElement('div', { classes: ['card', 'chart-card'] });
  const chartContainer = createElement('div', { classes: ['chart-container'] });
  chartCard.appendChild(chartContainer);

  const statusCard = createElement('div', { classes: ['card'] });
  const statusTitle = createElement('h4', { classes: ['section-heading__title'], text: 'وضعیت ربات' });
  const statusContent = createElement('div', { classes: ['status-row'] });
  statusCard.append(statusTitle, statusContent);

  const cacheCard = createElement('div', { classes: ['card'] });
  const cacheTitle = createElement('h4', { classes: ['section-heading__title'], text: 'کش و به‌روزرسانی' });
  const cacheMeta = createElement('p', { classes: ['card__meta'] });
  const cacheRelative = createElement('p', { classes: ['card__meta'] });
  cacheCard.append(cacheTitle, cacheMeta, cacheRelative);

  container.append(header, statsGrid, chartCard, cacheCard, statusCard);

  const loadingState = createLoadingState();
  container.appendChild(loadingState);

  let metrics = null;

  async function fetchData(showToast = false) {
    loadingState.textContent = 'در حال بارگذاری...';
    loadingState.hidden = false;
    try {
      metrics = await api.getMetrics();
      updateUI(metrics);
      if (showToast) {
        renderToast({ message: 'اطلاعات داشبورد به‌روزرسانی شد.' });
      }
    } catch (error) {
      console.error('Failed to load metrics', error);
      loadingState.textContent = 'دریافت داده با خطا مواجه شد.';
      renderToast({ message: 'بارگذاری داشبورد ناموفق بود.', type: 'error' });
    } finally {
      loadingState.hidden = true;
    }
  }

  function updateUI(data) {
    clearChildren(statsGrid);
    statsGrid.append(
      renderStatsCard({ label: 'کل مکالمات', value: data.totals.all }),
      renderStatsCard({ label: 'تلگرام', value: data.totals.telegram }),
      renderStatsCard({ label: 'تلگرام خصوصی', value: data.totals.privateTelegram ?? 0 }),
      renderStatsCard({ label: 'واتساپ', value: data.totals.whatsapp })
    );

    clearChildren(chartContainer);
    buildChart(chartContainer, data);

    cacheMeta.textContent = `آخرین به‌روزرسانی: ${formatDateTime(data.cache.lastUpdatedISO)}`;
    cacheRelative.textContent = `(${formatRelativeTime(data.cache.lastUpdatedISO)})`;

    clearChildren(statusContent);
    const { active, workingHours, message } = data.status;
    const toggleId = 'bot-status-toggle';
    const toggle = createToggle({
      id: toggleId,
      checked: active,
      label: 'تغییر وضعیت ربات',
      onChange: async (checked) => {
        try {
          await api.toggleBot(checked);
          renderToast({
            message: checked ? 'ربات فعال شد.' : 'ربات غیرفعال شد.',
          });
        } catch (error) {
          renderToast({ message: error.message, type: 'error' });
          toggle.input.checked = !checked;
        }
      },
    });

    const statusRow = createElement('div', { classes: ['status-row__item'] });
    statusRow.append(createElement('span', { text: 'وضعیت فعال بودن ربات' }), toggle.wrapper);
    const statusBadge = createBadge(active ? 'فعال' : 'غیرفعال', active ? 'success' : 'danger');

    const messageRow = createElement('div', { classes: ['status-row__item'] });
    messageRow.append(createElement('span', { text: 'وضعیت سرویس' }), statusBadge);

    const platformsRow = createElement('div', { classes: ['status-row__item', 'status-row__item--platforms'] });
    platformsRow.append(createElement('span', { text: 'پلتفرم‌ها' }));
    const platformValues = createElement('div', { classes: ['status-row__value', 'status-row__value--platforms'] });
    const platforms = data.status.platforms ?? {};
    [
      ['telegram', 'تلگرام'],
      ['privateTelegram', 'تلگرام خصوصی'],
      ['whatsapp', 'واتساپ'],
    ].forEach(([key, label]) => {
      const wrapper = createElement('span', { classes: ['status-row__platform'] });
      const badge = createBadge(platforms[key] ? 'فعال' : 'غیرفعال', platforms[key] ? 'success' : 'danger');
      wrapper.append(document.createTextNode(label), badge);
      platformValues.append(wrapper);
    });
    platformsRow.append(platformValues);

    const operations = data.status.operations ?? {};

    const lunchBreak = operations.lunchBreak ?? {};
    const lunchLabel = lunchBreak.start && lunchBreak.end
      ? `${lunchBreak.start} تا ${lunchBreak.end}`
      : 'تعریف نشده';
    const lunchRow = createElement('div', { classes: ['status-row__item'] });
    lunchRow.append(
      createElement('span', { text: 'استراحت ناهار' }),
      createElement('span', { classes: ['status-row__value'], text: lunchLabel })
    );

    const queryLimit = operations.queryLimit;
    const queryText =
      typeof queryLimit === 'number' && queryLimit > 0
        ? `${queryLimit} بار در روز`
        : 'بدون محدودیت';
    const queryRow = createElement('div', { classes: ['status-row__item'] });
    queryRow.append(
      createElement('span', { text: 'محدودیت استعلام' }),
      createElement('span', { classes: ['status-row__value'], text: queryText })
    );

    const deliveryInfo = operations.delivery ?? {};
    const deliverySummary = createElement('div', {
      classes: ['status-row__value', 'status-row__value--multiline'],
    });
    deliverySummary.append(
      createElement('span', {
        text: deliveryInfo.changeover ? `پس از ساعت ${deliveryInfo.changeover}` : 'ساعت تغییر تعریف نشده است',
      }),
      createElement('span', { text: `قبل: ${deliveryInfo.before ? deliveryInfo.before : '—'}` }),
      createElement('span', { text: `بعد: ${deliveryInfo.after ? deliveryInfo.after : '—'}` })
    );
    const deliveryRow = createElement('div', { classes: ['status-row__item'] });
    deliveryRow.append(createElement('span', { text: 'اطلاع‌رسانی تحویل' }), deliverySummary);

    const workingHoursList = renderWorkingHoursList(workingHours);
    const workingHoursWrapper = createElement('div', { classes: ['status-row__item'] });
    workingHoursWrapper.append(
      createElement('span', { text: `منطقه زمانی: ${workingHours.timezone}` }),
      workingHoursList
    );

    statusContent.append(
      statusRow,
      messageRow,
      platformsRow,
      createElement('p', { classes: ['status-row__message'], text: message }),
      lunchRow,
      queryRow,
      deliveryRow,
      workingHoursWrapper
    );
  }

  await fetchData();

  return {
    async refresh() {
      await fetchData(true);
    },
    destroy() {
      destroyChart();
    },
  };
}
