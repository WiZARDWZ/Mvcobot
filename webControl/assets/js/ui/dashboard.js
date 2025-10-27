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

let chartInstances = [];

function destroyCharts() {
  if (!chartInstances.length) {
    return;
  }
  chartInstances.forEach((instance) => {
    if (instance && typeof instance.destroy === 'function') {
      instance.destroy();
    }
  });
  chartInstances = [];
}

function getCssVar(name) {
  const style = getComputedStyle(document.documentElement);
  return style.getPropertyValue(name).trim() || name;
}

function computeTrend(monthly = [], key) {
  if (!Array.isArray(monthly) || monthly.length < 2) {
    return { direction: 'flat', percent: 0 };
  }
  const lastValue = Number(monthly[monthly.length - 1]?.[key] ?? 0);
  const previousValue = Number(monthly[monthly.length - 2]?.[key] ?? 0);
  if (previousValue === 0) {
    return {
      direction: lastValue === 0 ? 'flat' : 'up',
      percent: lastValue === 0 ? 0 : 100,
    };
  }
  const diff = lastValue - previousValue;
  const percent = (diff / previousValue) * 100;
  return {
    direction: diff === 0 ? 'flat' : diff > 0 ? 'up' : 'down',
    percent,
  };
}

function renderStatsCard({ label, value, trend, icon, variant }) {
  const card = createElement('div', {
    classes: ['card', 'stat-card', variant ? `stat-card--${variant}` : null].filter(Boolean),
  });

  const header = createElement('div', { classes: ['stat-card__header'] });
  header.append(
    createElement('span', { classes: ['stat-card__icon'], text: icon }),
    createElement('span', { classes: ['stat-card__label'], text: label })
  );

  const valueRow = createElement('div', { classes: ['stat-card__value-row'] });
  valueRow.append(
    createElement('span', {
      classes: ['stat-card__value'],
      text: Number(value ?? 0).toLocaleString('fa-IR'),
    })
  );

  if (trend) {
    const trendWrapper = createElement('span', {
      classes: ['stat-card__trend', `stat-card__trend--${trend.direction}`],
    });
    const arrow = trend.direction === 'down' ? '⬇️' : trend.direction === 'up' ? '⬆️' : '⟲';
    const percentText = Math.abs(trend.percent || 0).toLocaleString('fa-IR', {
      maximumFractionDigits: 1,
      minimumFractionDigits: 0,
    });
    trendWrapper.append(
      createElement('span', { classes: ['stat-card__trend-icon'], text: arrow }),
      createElement('span', {
        classes: ['stat-card__trend-value'],
        text: `${percentText}٪`,
      })
    );
    valueRow.append(trendWrapper);
  }

  card.append(header, valueRow);
  return card;
}

function buildChart(container, metrics) {
  destroyCharts();
  if (!window.Chart) {
    container.appendChild(
      createElement('p', {
        classes: ['card__meta'],
        text: 'امکان نمایش نمودار وجود ندارد. اسکریپت Chart.js در دسترس نیست.',
      })
    );
    return;
  }

  const { monthly = [] } = metrics || {};
  const labels = monthly.map((item) => item.month);
  const sparklineWrapper = createElement('div', {
    classes: ['analytics-card__sparklines'],
  });
  const aggregateWrapper = createElement('div', {
    classes: ['analytics-card__aggregate'],
  });

  const platformConfigs = [
    {
      key: 'whatsapp',
      label: 'واتساپ',
      color: getCssVar('--platform-whatsapp'),
      icon: '🟢',
    },
    {
      key: 'privateTelegram',
      label: 'تلگرام خصوصی',
      color: getCssVar('--platform-private-telegram'),
      icon: '🔐',
    },
    {
      key: 'telegram',
      label: 'تلگرام عمومی',
      color: getCssVar('--platform-telegram'),
      icon: '📣',
    },
  ];

  platformConfigs.forEach(({ key, label, color, icon }) => {
    const sparklineCard = createElement('div', {
      classes: ['sparkline-card', `sparkline-card--${key}`],
    });
    const cardHeader = createElement('div', { classes: ['sparkline-card__header'] });
    cardHeader.append(
      createElement('span', { classes: ['sparkline-card__icon'], text: icon }),
      createElement('span', { classes: ['sparkline-card__title'], text: label })
    );

    const latestValue = Number(monthly[monthly.length - 1]?.[key] ?? 0).toLocaleString('fa-IR');
    cardHeader.append(
      createElement('span', {
        classes: ['sparkline-card__meta'],
        text: `${latestValue} در ماه اخیر`,
      })
    );

    const canvas = createElement('canvas', {
      attrs: { 'aria-label': `روند ${label}` },
    });

    sparklineCard.append(cardHeader, canvas);
    sparklineWrapper.append(sparklineCard);

    const ctx = canvas.getContext('2d');
    const dataset = monthly.map((item) => Number(item?.[key] ?? 0));
    const chart = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            data: dataset,
            borderColor: color,
            backgroundColor: color,
            fill: false,
            tension: 0.35,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            rtl: true,
            callbacks: {
              label(context) {
                const value = Number(context.parsed.y ?? 0).toLocaleString('fa-IR');
                return `${label}: ${value}`;
              },
            },
          },
        },
        scales: {
          x: {
            display: false,
          },
          y: {
            display: false,
          },
        },
      },
    });
    chartInstances.push(chart);
  });

  const aggregateCanvas = createElement('canvas', {
    attrs: { 'aria-label': 'نمودار تجمیعی تعاملات ماهانه' },
  });
  aggregateWrapper.append(aggregateCanvas);

  const aggregateCtx = aggregateCanvas.getContext('2d');
  const aggregateChart = new window.Chart(aggregateCtx, {
    type: 'line',
    data: {
      labels,
      datasets: platformConfigs.map(({ key, label, color }) => ({
        label,
        data: monthly.map((item) => Number(item?.[key] ?? 0)),
        borderColor: color,
        backgroundColor: color,
        fill: false,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: {
          position: 'bottom',
          align: 'start',
          labels: {
            usePointStyle: true,
            font: {
              family: 'Vazirmatn, system-ui',
            },
          },
        },
        tooltip: {
          rtl: true,
          callbacks: {
            label(context) {
              const value = Number(context.parsed.y ?? 0).toLocaleString('fa-IR');
              return `${context.dataset.label}: ${value}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            maxRotation: 0,
            autoSkipPadding: 8,
          },
          grid: {
            color: 'rgba(148, 163, 184, 0.2)',
          },
        },
        y: {
          ticks: {
            callback(value) {
              return Number(value).toLocaleString('fa-IR');
            },
          },
          grid: {
            color: 'rgba(148, 163, 184, 0.2)',
          },
        },
      },
    },
  });

  chartInstances.push(aggregateChart);
  container.append(sparklineWrapper, aggregateWrapper);
}

export async function mount(container) {
  const header = createElement('div', { classes: ['dashboard-header'] });
  const breadcrumb = createElement('nav', {
    classes: ['dashboard-breadcrumb'],
    attrs: { 'aria-label': 'آدرس راهبری' },
  });
  breadcrumb.append(
    createElement('span', { classes: ['dashboard-breadcrumb__item'], text: 'خانه' }),
    createElement('span', { classes: ['dashboard-breadcrumb__separator'], text: '›' }),
    createElement('span', { classes: ['dashboard-breadcrumb__item', 'is-current'], text: 'داشبورد' })
  );

  header.append(breadcrumb);

  const layout = createElement('div', { classes: ['dashboard-layout'] });

  const statsGrid = createElement('div', { classes: ['dashboard-stats'] });

  const analyticsCard = createElement('section', { classes: ['card', 'analytics-card'] });
  const analyticsTitle = createElement('h4', {
    classes: ['card__title'],
    text: 'تحلیل تعاملات',
  });
  const chartContainer = createElement('div', { classes: ['analytics-card__body'] });
  analyticsCard.append(analyticsTitle, chartContainer);

  const statusCard = createElement('section', { classes: ['card', 'status-card'] });
  const statusTitle = createElement('h4', { classes: ['card__title'], text: 'وضعیت ربات' });
  const statusContent = createElement('div', { classes: ['status-card__content'] });
  statusCard.append(statusTitle, statusContent);

  const cacheCard = createElement('section', { classes: ['card', 'cache-card'] });
  const cacheTitle = createElement('h4', { classes: ['card__title'], text: 'کش و به‌روزرسانی' });
  const cacheMeta = createElement('p', { classes: ['cache-card__meta'] });
  const cacheRelative = createElement('p', { classes: ['cache-card__meta', 'cache-card__meta--muted'] });
  cacheCard.append(cacheTitle, cacheMeta, cacheRelative);

  const hoursCard = createElement('section', { classes: ['card', 'hours-card'] });
  const hoursTitle = createElement('h4', { classes: ['card__title'], text: 'ساعات کاری' });
  const hoursTimezone = createElement('p', { classes: ['hours-card__timezone'] });
  const hoursListWrapper = createElement('div', { classes: ['hours-card__list'] });
  hoursCard.append(hoursTitle, hoursTimezone, hoursListWrapper);

  layout.append(statsGrid, analyticsCard, statusCard, cacheCard, hoursCard);
  container.append(header, layout);

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
    const monthly = Array.isArray(data.monthly) ? data.monthly : [];

    clearChildren(statsGrid);
    [
      {
        key: 'whatsapp',
        label: 'واتساپ',
        icon: '🟢',
        variant: 'whatsapp',
        value: data.totals.whatsapp,
      },
      {
        key: 'privateTelegram',
        label: 'تلگرام خصوصی',
        icon: '🔐',
        variant: 'private',
        value: data.totals.privateTelegram ?? 0,
      },
      {
        key: 'telegram',
        label: 'تلگرام عمومی',
        icon: '📣',
        variant: 'telegram',
        value: data.totals.telegram,
      },
      {
        key: 'all',
        label: 'کل تعاملات',
        icon: '📊',
        variant: 'all',
        value: data.totals.all,
      },
    ].forEach((item) => {
      statsGrid.append(
        renderStatsCard({
          label: item.label,
          value: item.value,
          trend: computeTrend(monthly, item.key),
          icon: item.icon,
          variant: item.variant,
        })
      );
    });

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

    const statusRow = createElement('div', { classes: ['status-card__row'] });
    statusRow.append(createElement('span', { classes: ['status-card__label'], text: 'فعال بودن ربات' }), toggle.wrapper);
    const statusBadge = createBadge(active ? 'فعال' : 'غیرفعال', active ? 'success' : 'danger');

    const messageRow = createElement('div', { classes: ['status-card__chips'] });
    messageRow.append(statusBadge);

    const platformsRow = createElement('div', { classes: ['status-card__platforms'] });
    const platforms = data.status.platforms ?? {};
    [
      ['telegram', 'تلگرام'],
      ['privateTelegram', 'تلگرام خصوصی'],
      ['whatsapp', 'واتساپ'],
    ].forEach(([key, label]) => {
      const wrapper = createElement('span', { classes: ['status-card__platform'] });
      const badge = createBadge(platforms[key] ? 'فعال' : 'غیرفعال', platforms[key] ? 'success' : 'danger');
      wrapper.append(document.createTextNode(label), badge);
      platformsRow.append(wrapper);
    });

    const operations = data.status.operations ?? {};

    const lunchBreak = operations.lunchBreak ?? {};
    const lunchLabel = lunchBreak.start && lunchBreak.end
      ? `${lunchBreak.start} تا ${lunchBreak.end}`
      : 'تعریف نشده';
    const lunchRow = createElement('div', { classes: ['status-card__meta-item'] });
    lunchRow.append(
      createElement('span', { classes: ['status-card__meta-label'], text: 'استراحت ناهار' }),
      createElement('span', { classes: ['status-card__meta-value'], text: lunchLabel })
    );

    const deliveryInfo = operations.delivery ?? {};
    const deliverySummary = createElement('div', {
      classes: ['status-card__meta-value', 'status-card__meta-value--stacked'],
    });
    deliverySummary.append(
      createElement('span', {
        text: deliveryInfo.changeover ? `پس از ساعت ${deliveryInfo.changeover}` : 'ساعت تغییر تعریف نشده است',
      }),
      createElement('span', { text: `قبل: ${deliveryInfo.before ? deliveryInfo.before : '—'}` }),
      createElement('span', { text: `بعد: ${deliveryInfo.after ? deliveryInfo.after : '—'}` })
    );
    const deliveryRow = createElement('div', { classes: ['status-card__meta-item'] });
    deliveryRow.append(
      createElement('span', { classes: ['status-card__meta-label'], text: 'اطلاع‌رسانی تحویل' }),
      deliverySummary
    );

    const fallbackRow = createElement('div', { classes: ['status-card__meta-item'] });
    const fallbackBadge = createBadge(
      data.status.usingFallback ? 'حالت پشتیبان فعال' : 'اتصال مستقیم',
      data.status.usingFallback ? 'danger' : 'success'
    );
    fallbackRow.append(
      createElement('span', { classes: ['status-card__meta-label'], text: 'وضعیت پایگاه‌داده' }),
      fallbackBadge
    );

    statusContent.append(
      statusRow,
      messageRow,
      createElement('p', { classes: ['status-card__message'], text: message }),
      platformsRow,
      lunchRow,
      deliveryRow,
      fallbackRow
    );

    hoursTimezone.textContent = `منطقه زمانی: ${workingHours.timezone ?? 'تعریف نشده'}`;
    clearChildren(hoursListWrapper);
    hoursListWrapper.append(renderWorkingHoursList(workingHours));
  }

  await fetchData();

  return {
    async refresh() {
      await fetchData(true);
    },
    destroy() {
      destroyCharts();
    },
  };
}
