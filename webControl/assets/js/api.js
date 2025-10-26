/**
 * API layer for the Mvcobot control panel.
 * Provides a mock data store that can be swapped with the real backend by
 * configuring window.APP_CONFIG.API_BASE_URL.
 */

const defaultConfig = {
  API_BASE_URL: '',
  API_KEY: '',
  TELEGRAM_ENABLED: true,
  WHATSAPP_ENABLED: true,
  PRIVATE_TELEGRAM_ENABLED: true,
};

const DEFAULT_FALLBACK_MESSAGE =
  'اتصال به پایگاه‌داده برقرار نیست؛ داده‌های نمونه نمایش داده می‌شوند.';

const DEFAULT_WEEKLY_SCHEDULE = [
  { day: 5, open: '09:00', close: '18:00' },
  { day: 6, open: '09:00', close: '18:00' },
  { day: 0, open: '09:00', close: '18:00' },
  { day: 1, open: '09:00', close: '18:00' },
  { day: 2, open: '09:00', close: '18:00' },
  { day: 3, open: '09:00', close: '18:00' },
  { day: 4, open: null, close: null },
];

const seededRandom = (() => {
  let seed = 42;
  return () => {
    const x = Math.sin(seed++) * 10000;
    return x - Math.floor(x);
  };
})();

function getLastMonths(count = 12) {
  const now = new Date();
  const months = [];
  for (let i = count - 1; i >= 0; i -= 1) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const label = new Intl.DateTimeFormat('fa-IR', { month: 'short' }).format(date);
    months.push({
      month: label,
      key: `${date.getFullYear()}-${date.getMonth() + 1}`.padStart(2, '0'),
    });
  }
  return months;
}

const monthlyData = getLastMonths(12).map(({ month }) => {
  const telegram = Math.floor(seededRandom() * 120 + 30);
  const whatsapp = Math.floor(seededRandom() * 180 + 45);
  const privateTelegram = Math.floor(seededRandom() * 90 + 20);
  return {
    month,
    telegram,
    whatsapp,
    privateTelegram,
    all: telegram + whatsapp + privateTelegram,
  };
});

const samplePartNames = [
  'سنسور اکسیژن',
  'پمپ بنزین',
  'چراغ جلو',
  'سوییچ اصلی',
  'لنت ترمز جلو',
  'سیبک فرمان',
  'کمک فنر عقب',
  'فیلتر هوای موتور',
  'رادیاتور آب',
  'میل موجگیر',
];

const codeStatsBase = Array.from({ length: 60 }, (_, index) => {
  const raw = `${Math.floor(seededRandom() * 9000000000) + 1000000000}`;
  const code = `${raw.slice(0, 5)}-${raw.slice(5, 10)}`;
  const partName = samplePartNames[index % samplePartNames.length];
  const baseCount = Math.floor(seededRandom() * 180 + 15);
  return { code, partName, baseCount };
});

function buildMockCodeStats({ rangeKey, sortOrder, page, pageSize, searchTerm = '' }) {
  const factors = {
    '1m': 0.65,
    '2m': 0.8,
    '3m': 0.9,
    '6m': 1,
    '1y': 1.15,
    all: 1.3,
  };
  const key = (rangeKey || '1m').toLowerCase();
  const factor = factors[key] ?? factors['1m'];
  const direction = (sortOrder || 'desc').toLowerCase().startsWith('a') ? 'asc' : 'desc';

  const enriched = codeStatsBase.map((item) => {
    const jitter = Math.floor(seededRandom() * 12);
    const requestCount = Math.max(1, Math.round(item.baseCount * factor + jitter));
    return { code: item.code, partName: item.partName, requestCount };
  });

  const searchValue = (searchTerm || '').trim().toUpperCase();
  let working = enriched.slice();
  if (searchValue) {
    const normalizedSearch = searchValue.replace(/[^A-Z0-9]/g, '');
    working = working.filter((item) => {
      const normalizedCode = item.code.replace(/-/g, '');
      if (normalizedSearch && normalizedCode.includes(normalizedSearch)) {
        return true;
      }
      return item.code.toUpperCase().includes(searchValue);
    });
  }

  working.sort((a, b) => {
    if (a.requestCount === b.requestCount) {
      return a.code.localeCompare(b.code, 'fa');
    }
    return direction === 'asc'
      ? a.requestCount - b.requestCount
      : b.requestCount - a.requestCount;
  });

  const total = working.length;
  const safePageSize = Math.max(1, pageSize);
  const pages = Math.max(1, Math.ceil(total / safePageSize));
  const safePage = Math.min(Math.max(1, page), pages);
  const startIndex = (safePage - 1) * safePageSize;
  const items = working.slice(startIndex, startIndex + safePageSize);

  return {
    items,
    page: safePage,
    pageSize: safePageSize,
    total,
    pages,
  };
}

const EXCEL_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

const PEAK_PERIOD_LABELS = {
  day: 'روز',
  month: 'ماه',
  year: 'سال',
};

function ensureXlsxFileName(value, referenceDate = new Date()) {
  const base = referenceDate instanceof Date && !Number.isNaN(referenceDate.valueOf())
    ? referenceDate.toISOString().slice(0, 10)
    : 'report';
  const trimmed = (value ?? '').toString().trim();
  const safe = (trimmed || `گزارش-آمار-${base}`).replace(/[\\/:*?"<>|]+/g, '-');
  return safe.toLowerCase().endsWith('.xlsx') ? safe : `${safe}.xlsx`;
}

function escapeExcelXml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function columnLetter(index) {
  let dividend = index;
  let columnName = '';
  while (dividend > 0) {
    const modulo = (dividend - 1) % 26;
    columnName = String.fromCharCode(65 + modulo) + columnName;
    dividend = Math.floor((dividend - modulo) / 26);
  }
  return columnName || 'A';
}

function formatReportDate(value) {
  if (!value) return 'نامشخص';
  try {
    const date = new Date(value);
    if (Number.isNaN(date.valueOf())) {
      return 'نامشخص';
    }
    return new Intl.DateTimeFormat('fa-IR', {
      year: 'numeric',
      month: 'long',
      day: '2-digit',
    }).format(date);
  } catch (error) {
    return 'نامشخص';
  }
}

function formatReportDateTime(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return 'نامشخص';
  }
  return new Intl.DateTimeFormat('fa-IR', {
    year: 'numeric',
    month: 'long',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function resolvePeakPeriodLabel(value) {
  return PEAK_PERIOD_LABELS[value] ?? 'نامشخص';
}

function resolveMockRangeKey(peakPeriod) {
  if (peakPeriod === 'month') return '3m';
  if (peakPeriod === 'year') return '1y';
  return '1m';
}

async function createExcelBlob(rows) {
  const { default: JSZip } = await import('https://cdn.jsdelivr.net/npm/jszip@3.10.1/+esm');
  const zip = new JSZip();
  const maxColumns = rows.reduce((max, row) => Math.max(max, row.length), 0) || 1;
  const normalizedRows = rows.map((row) => {
    const next = Array.from(row);
    while (next.length < maxColumns) {
      next.push('');
    }
    return next;
  });

  const dimension = `A1:${columnLetter(maxColumns)}${normalizedRows.length}`;
  const sheetRowsXml = normalizedRows
    .map((row, rowIndex) => {
      const cells = row
        .map((value, cellIndex) => {
          const cellRef = `${columnLetter(cellIndex + 1)}${rowIndex + 1}`;
          const text = value == null ? '' : String(value);
          return `<c r="${cellRef}" t="inlineStr"><is><t>${escapeExcelXml(text)}</t></is></c>`;
        })
        .join('');
      return `<row r="${rowIndex + 1}">${cells}</row>`;
    })
    .join('\n');

  const columnWidths = Array.from({ length: maxColumns }, (_, index) => {
    if (index === 2) return 18;
    if (index === 1) return 34;
    return 28;
  });

  const colsXml = columnWidths
    .map((width, index) => {
      const position = index + 1;
      return `<col min="${position}" max="${position}" width="${width}" customWidth="1"/>`;
    })
    .join('\n    ');

  const sheetXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetViews>
    <sheetView workbookViewId="0" rightToLeft="1"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <dimension ref="${dimension}"/>
  <cols>
    ${colsXml}
  </cols>
  <sheetData>
${sheetRowsXml}
  </sheetData>
</worksheet>`;

  const workbookXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <fileVersion appName="xl"/>
  <workbookPr date1904="false"/>
  <bookViews>
    <workbookView xWindow="0" yWindow="0" windowWidth="28800" windowHeight="17600"/>
  </bookViews>
  <sheets>
    <sheet name="گزارش" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>`;

  const workbookRelsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`;

  const stylesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1">
    <font>
      <sz val="11"/>
      <name val="Calibri"/>
    </font>
  </fonts>
  <fills count="1">
    <fill>
      <patternFill patternType="none"/>
    </fill>
  </fills>
  <borders count="1">
    <border>
      <left/>
      <right/>
      <top/>
      <bottom/>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>`;

  const contentTypesXml = `<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>`;

  const rootRelsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>`;

  const now = new Date();
  const docPropsCore = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>Mvcobot Control Panel</dc:creator>
  <cp:lastModifiedBy>Mvcobot Control Panel</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">${now.toISOString()}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">${now.toISOString()}</dcterms:modified>
</cp:coreProperties>`;

  const docPropsApp = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Mvcobot</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant>
        <vt:lpstr>Worksheets</vt:lpstr>
      </vt:variant>
      <vt:variant>
        <vt:i4>1</vt:i4>
      </vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>گزارش</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
  <Company>Mvcobot</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0300</AppVersion>
</Properties>`;

  zip.file('[Content_Types].xml', contentTypesXml);
  zip.folder('_rels').file('.rels', rootRelsXml);
  const docProps = zip.folder('docProps');
  docProps.file('core.xml', docPropsCore);
  docProps.file('app.xml', docPropsApp);
  const xl = zip.folder('xl');
  xl.file('workbook.xml', workbookXml);
  xl.folder('_rels').file('workbook.xml.rels', workbookRelsXml);
  xl.file('styles.xml', stylesXml);
  xl.folder('worksheets').file('sheet1.xml', sheetXml);

  return zip.generateAsync({ type: 'blob', mimeType: EXCEL_MIME_TYPE });
}

async function buildExcelExportMock({
  from,
  to,
  motherCode,
  productName,
  requestCount,
  peakPeriod,
  fileName,
}) {
  const now = new Date();
  const safeFileName = ensureXlsxFileName(fileName, now);
  const normalizedRequestCount = Number.isFinite(Number(requestCount))
    ? Number(requestCount)
    : null;

  const summaryRows = [
    ['فیلد', 'مقدار', ''],
    ['بازه تاریخ (از)', formatReportDate(from), ''],
    ['بازه تاریخ (تا)', formatReportDate(to), ''],
    ['کد مادر (قبل از ساده‌سازی)', motherCode ? String(motherCode).trim() : '—', ''],
    ['نام کالا', productName ? String(productName).trim() : '—', ''],
    [
      'تعداد درخواست',
      normalizedRequestCount !== null ? normalizedRequestCount.toLocaleString('fa-IR') : 'نامشخص',
      '',
    ],
    ['بازه زمانی با بیشترین درخواست', resolvePeakPeriodLabel(peakPeriod), ''],
  ];

  const statsSnapshot = buildMockCodeStats({
    rangeKey: resolveMockRangeKey(peakPeriod),
    sortOrder: 'desc',
    page: 1,
    pageSize: 10,
  });

  const tableHeader = ['کد قطعه', 'نام قطعه', 'تعداد درخواست'];
  const tableRows = statsSnapshot.items.map((item) => [
    item.code,
    item.partName,
    item.requestCount.toLocaleString('fa-IR'),
  ]);

  const rows = [
    ...summaryRows,
    ['', '', ''],
    tableHeader,
    ...tableRows,
    ['', '', ''],
    ['تاریخ تهیه گزارش', formatReportDateTime(now), ''],
  ];

  const blob = await createExcelBlob(rows);

  return {
    fileName: safeFileName,
    blob,
    generatedAt: now.toISOString(),
  };
}

export const API_EVENTS = {
  FALLBACK: 'mvcobot:api-fallback',
};

const mockStore = {
  metrics: {
    totals: monthlyData.reduce(
      (acc, item) => ({
        telegram: acc.telegram + item.telegram,
        whatsapp: acc.whatsapp + item.whatsapp,
        privateTelegram: acc.privateTelegram + item.privateTelegram,
        all: acc.all + item.all,
      }),
      { telegram: 0, whatsapp: 0, privateTelegram: 0, all: 0 }
    ),
    monthly: monthlyData,
    cache: {
      lastUpdatedISO: new Date(Date.now() - 1000 * 60 * 32).toISOString(),
      usingFallback: true,
    },
    status: {
      active: true,
      workingHours: {
        timezone: 'Asia/Tehran',
        weekly: DEFAULT_WEEKLY_SCHEDULE.map((item) => ({ ...item })),
      },
      message: 'ربات فعال و آماده پاسخ‌گویی است.',
      platforms: {
        telegram: defaultConfig.TELEGRAM_ENABLED,
        whatsapp: defaultConfig.WHATSAPP_ENABLED,
        privateTelegram: defaultConfig.PRIVATE_TELEGRAM_ENABLED,
      },
      operations: {
        lunchBreak: { start: '12:30', end: '13:30' },
        queryLimit: 50,
        delivery: {
          before: 'تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها ساعت 12:30 در دفتر بازار',
          after: 'ارسال مستقیم از انبار با زمان تقریبی تحویل 45 دقیقه امکان‌پذیر است.',
          changeover: '15:30',
        },
      },
      dataSource: 'fallback',
      usingFallback: true,
    },
  },
  commands: [
    {
      id: 'cmd-1',
      command: '/start',
      description: 'آغاز مکالمه با کاربر و ارسال راهنما',
      enabled: true,
      lastUsedISO: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
    },
    {
      id: 'cmd-2',
      command: '/pricing',
      description: 'ارائه پلن‌های قیمت به کاربر',
      enabled: true,
      lastUsedISO: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
    },
    {
      id: 'cmd-3',
      command: '/support',
      description: 'اتصال کاربر به پشتیبانی انسانی',
      enabled: false,
      lastUsedISO: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
    },
  ],
  blocklist: [
    {
      id: 'blk-1',
      platform: 'telegram',
      phoneOrUser: '@spam_account',
      reason: 'ارسال پیام تبلیغاتی',
      createdAtISO: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(),
    },
    {
      id: 'blk-2',
      platform: 'whatsapp',
      phoneOrUser: '+982112345678',
      reason: 'گزارش تخلف کاربران',
      createdAtISO: new Date(Date.now() - 1000 * 60 * 60 * 24 * 12).toISOString(),
    },
  ],
  settings: {
    timezone: 'Asia/Tehran',
    weekly: DEFAULT_WEEKLY_SCHEDULE.map((item) => ({ ...item })),
    platforms: {
      telegram: defaultConfig.TELEGRAM_ENABLED,
      whatsapp: defaultConfig.WHATSAPP_ENABLED,
      privateTelegram: defaultConfig.PRIVATE_TELEGRAM_ENABLED,
    },
    lunchBreak: { start: '12:30', end: '13:30' },
    queryLimit: 50,
    deliveryInfo: {
      before: 'تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها ساعت 12:30 در دفتر بازار',
      after: 'ارسال مستقیم از انبار با زمان تقریبی تحویل 45 دقیقه امکان‌پذیر است.',
      changeover: '15:30',
    },
    dataSource: 'fallback',
  },
  auditLog: [
    {
      id: 'log-1',
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
      message: 'به‌روزرسانی تنظیمات',
      details: 'ساعات کاری، پلتفرم‌ها',
      actor: 'کنترل‌پنل',
    },
    {
      id: 'log-2',
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
      message: 'تغییر وضعیت ربات',
      details: 'فعال',
      actor: 'کنترل‌پنل',
    },
    {
      id: 'log-3',
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 12).toISOString(),
      message: 'به‌روزرسانی کش کالا',
      details: 'نمونه',
      actor: 'کنترل‌پنل',
    },
  ],
  privateTelegram: {
    enabled: true,
    dmEnabled: true,
    apiId: 123456,
    apiHash: 'samplehash',
    phoneNumber: '+989120000000',
    dataSource: 'sql',
    excelFile: 'inventory.xlsx',
    cacheDurationMinutes: 20,
    mainGroupId: -1001234567890,
    newGroupId: -1001987654321,
    adminGroupIds: [-1001987654321],
    secondaryGroupIds: [-1001122334455],
    workingHours: { start: '08:00', end: '17:30' },
    thursdayHours: { start: '08:00', end: '13:30' },
    disableFriday: true,
    lunchBreak: { start: '14:00', end: '14:30' },
    queryLimit: 50,
    deliveryInfo: {
      before15: 'تحویل کالا پیش از ساعت ۱۵ از دفتر بازار انجام می‌شود.',
      after15: 'پس از ساعت ۱۵ تحویل با هماهنگی پیک انجام خواهد شد.',
    },
    changeoverHour: '15:00',
    blacklist: [437739989],
    dataSourceOrigin: 'mock',
  },
  codeStats: codeStatsBase,
};

const delay = (ms = 360) => new Promise((resolve) => setTimeout(resolve, ms));

function getConfig() {
  return { ...defaultConfig, ...(window.APP_CONFIG ?? {}) };
}

function isMockMode() {
  const { API_BASE_URL } = getConfig();
  return API_BASE_URL === null || typeof API_BASE_URL === 'undefined';
}

function withAuthHeaders(headers = {}) {
  const { API_KEY } = getConfig();
  if (API_KEY) {
    return {
      ...headers,
      Authorization: `Bearer ${API_KEY}`,
    };
  }
  return headers;
}

async function request(path, { method = 'GET', body } = {}) {
  const { API_BASE_URL } = getConfig();
  let base = '';
  if (typeof API_BASE_URL === 'string') {
    base = API_BASE_URL.trim();
  }
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base;
  const url = normalizedBase ? `${normalizedBase}${path}` : path;
  const options = {
    method,
    headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
    body: body ? JSON.stringify(body) : undefined,
  };
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (error) {
      data = text;
    }
  }
  if (!response.ok) {
    const message = data?.message || response.statusText || 'خطای ناشناخته';
    throw new Error(message);
  }
  return data;
}

function clone(data) {
  if (typeof structuredClone === 'function') {
    return structuredClone(data);
  }
  return JSON.parse(JSON.stringify(data));
}

function emitFallback(detail) {
  const payload = {
    message: DEFAULT_FALLBACK_MESSAGE,
    ...detail,
  };
  try {
    window.dispatchEvent(new CustomEvent(API_EVENTS.FALLBACK, { detail: payload }));
  } catch (error) {
    // ignored: running outside the browser
  }
}

async function runMock(handler) {
  await delay();
  const result = await handler();
  if (result instanceof Blob) {
    return result;
  }
  if (result && typeof result === 'object' && 'blob' in result && result.blob instanceof Blob) {
    const { blob, ...rest } = result;
    return { ...clone(rest), blob };
  }
  return clone(result);
}

async function runWithFallback(method, requestFn, mockFn) {
  if (isMockMode()) {
    return runMock(mockFn);
  }

  try {
    return await requestFn();
  } catch (error) {
    console.warn(`API request failed for ${method}. Falling back to mock data.`, error);
    emitFallback({ method, error });
    return runMock(mockFn);
  }
}

function ensureId(prefix) {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${prefix}-${Math.random().toString(16).slice(2)}-${Date.now()}`;
}

function pushMockAudit(message, details) {
  const entry = {
    id: ensureId('log'),
    timestamp: new Date().toISOString(),
    message,
    actor: 'کنترل‌پنل',
  };
  if (details) {
    entry.details = details;
  }
  mockStore.auditLog.unshift(entry);
  mockStore.auditLog = mockStore.auditLog.slice(0, 50);
  return entry;
}

export const api = {
  async getMetrics() {
    const result = await runWithFallback(
      'getMetrics',
      () => request('/api/v1/metrics'),
      () => mockStore.metrics
    );
    if (
      isMockMode() ||
      result?.cache?.usingFallback ||
      result?.status?.usingFallback ||
      result?.status?.dataSource === 'fallback'
    ) {
      emitFallback({ method: 'getMetrics', reason: 'usingFallback' });
    }
    return result;
  },

  async getCodeStats({ range = '1m', sort = 'desc', page = 1, pageSize = 20, search = '' } = {}) {
    const params = new URLSearchParams({
      range,
      sort,
      page: String(page),
      pageSize: String(pageSize),
    });
    if (search && search.trim()) {
      params.set('search', search.trim());
    }

    const mockHandler = () => {
      const snapshot = buildMockCodeStats({
        rangeKey: range,
        sortOrder: sort,
        page,
        pageSize,
        searchTerm: search,
      });
      return {
        items: snapshot.items.map((item) => ({
          code: item.code,
          partName: item.partName,
          requestCount: item.requestCount,
        })),
        page: snapshot.page,
        pageSize: snapshot.pageSize,
        total: snapshot.total,
        pages: snapshot.pages,
        range,
        sort,
        search,
      };
    };

    return runWithFallback(
      'getCodeStats',
      () => request(`/api/v1/code-stats?${params.toString()}`),
      mockHandler
    );
  },

  async exportCodeStatsToExcel(filters = {}) {
    const payload = {
      from: filters.dateFrom ?? null,
      to: filters.dateTo ?? null,
      motherCode: filters.motherCode ?? null,
      productName: filters.productName ?? null,
      requestCount:
        typeof filters.requestCount === 'number' && !Number.isNaN(filters.requestCount)
          ? filters.requestCount
          : filters.requestCount && !Number.isNaN(Number(filters.requestCount))
          ? Number(filters.requestCount)
          : null,
      peakPeriod: filters.peakPeriod ?? 'day',
      fileName: filters.fileName ?? null,
    };

    const mockHandler = () => buildExcelExportMock(payload);

    const response = await runWithFallback(
      'exportCodeStatsToExcel',
      async () => {
        const result = await request('/api/v1/code-stats/export', {
          method: 'POST',
          body: payload,
        });
        if (!result) {
          throw new Error('پاسخی از سرور دریافت نشد.');
        }
        if (result.blob && result.fileName) {
          return {
            fileName: ensureXlsxFileName(result.fileName),
            blob: result.blob,
          };
        }
        if (result.content && typeof result.content === 'string') {
          const binary = atob(result.content);
          const length = binary.length;
          const buffer = new Uint8Array(length);
          for (let i = 0; i < length; i += 1) {
            buffer[i] = binary.charCodeAt(i);
          }
          const blob = new Blob([buffer], { type: EXCEL_MIME_TYPE });
          return {
            fileName: ensureXlsxFileName(result.fileName ?? payload.fileName),
            blob,
          };
        }
        throw new Error('ساختار خروجی ناشناخته است.');
      },
      mockHandler
    );

    return response;
  },

  async refreshCodeNames({ limit } = {}) {
    const payload = {};
    if (typeof limit !== 'undefined' && limit !== null) {
      const numericLimit = Number(limit);
      if (!Number.isNaN(numericLimit)) {
        payload.limit = numericLimit;
      }
    }

    const mockHandler = async () => {
      await delay(180);
      return { updated: 0, limit: payload.limit ?? null };
    };

    const body = Object.keys(payload).length ? payload : {};

    return runWithFallback(
      'refreshCodeNames',
      () =>
        request('/api/v1/code-stats/refresh-names', {
          method: 'POST',
          body,
        }),
      mockHandler
    );
  },

  async getCommands() {
    return runWithFallback(
      'getCommands',
      () => request('/api/v1/commands'),
      () => mockStore.commands
    );
  },

  async createCommand(payload) {
    const mockHandler = () => {
      const item = {
        id: ensureId('cmd'),
        lastUsedISO: null,
        ...payload,
      };
      mockStore.commands.unshift(item);
      pushMockAudit('ثبت دستور جدید', `${item.command} (شناسه ${item.id})`);
      return item;
    };

    return runWithFallback(
      'createCommand',
      () => request('/api/v1/commands', { method: 'POST', body: payload }),
      mockHandler
    );
  },

  async updateCommand(id, payload) {
    const mockHandler = () => {
      const index = mockStore.commands.findIndex((item) => item.id === id);
      if (index === -1) throw new Error('دستور یافت نشد');
      mockStore.commands[index] = { ...mockStore.commands[index], ...payload };
      pushMockAudit('ویرایش دستور', `${mockStore.commands[index].command} (شناسه ${id})`);
      return mockStore.commands[index];
    };

    return runWithFallback(
      'updateCommand',
      () => request(`/api/v1/commands/${id}`, { method: 'PUT', body: payload }),
      mockHandler
    );
  },

  async deleteCommand(id) {
    const mockHandler = () => {
      mockStore.commands = mockStore.commands.filter((item) => item.id !== id);
      pushMockAudit('حذف دستور', `شناسه ${id}`);
      return { success: true };
    };

    return runWithFallback(
      'deleteCommand',
      () => request(`/api/v1/commands/${id}`, { method: 'DELETE' }),
      mockHandler
    );
  },

  async getBlocklist() {
    return runWithFallback(
      'getBlocklist',
      () => request('/api/v1/blocklist'),
      () => mockStore.blocklist
    );
  },

  async addBlockItem(payload) {
    const mockHandler = () => {
      const item = {
        id: ensureId('blk'),
        createdAtISO: new Date().toISOString(),
        ...payload,
      };
      mockStore.blocklist.unshift(item);
      pushMockAudit('افزودن به لیست مسدود', payload.userId || payload.phoneOrUser);
      return item;
    };

    return runWithFallback(
      'addBlockItem',
      () => request('/api/v1/blocklist', { method: 'POST', body: payload }),
      mockHandler
    );
  },

  async removeBlockItem(id) {
    const mockHandler = () => {
      mockStore.blocklist = mockStore.blocklist.filter((item) => item.id !== id);
      pushMockAudit('حذف از لیست مسدود', `شناسه ${id}`);
      return { success: true };
    };

    return runWithFallback(
      'removeBlockItem',
      () => request(`/api/v1/blocklist/${id}`, { method: 'DELETE' }),
      mockHandler
    );
  },

  async getSettings() {
    const result = await runWithFallback(
      'getSettings',
      () => request('/api/v1/settings'),
      () => mockStore.settings
    );
    if (isMockMode() || result?.dataSource === 'fallback') {
      emitFallback({ method: 'getSettings', reason: 'usingFallback' });
    }
    return result;
  },

  async updateSettings(payload) {
    const mockHandler = () => {
      mockStore.settings = {
        ...mockStore.settings,
        ...payload,
      };
      if (payload.platforms) {
        mockStore.settings.platforms = {
          ...mockStore.settings.platforms,
          ...payload.platforms,
        };
        mockStore.metrics.status.platforms = {
          ...mockStore.metrics.status.platforms,
          ...mockStore.settings.platforms,
        };
      }
      if (payload.weekly) {
        mockStore.settings.weekly = payload.weekly.map((item) => ({ ...item }));
      }
      if (payload.weekly || payload.timezone) {
        mockStore.metrics.status.workingHours = {
          timezone: payload.timezone ?? mockStore.settings.timezone,
          weekly: (payload.weekly ?? mockStore.settings.weekly).map((item) => ({ ...item })),
        };
      }
      if (payload.lunchBreak) {
        mockStore.settings.lunchBreak = {
          start: payload.lunchBreak.start ?? null,
          end: payload.lunchBreak.end ?? null,
        };
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'queryLimit')) {
        mockStore.settings.queryLimit = payload.queryLimit ?? null;
      }
      if (payload.deliveryInfo) {
        mockStore.settings.deliveryInfo = {
          before: payload.deliveryInfo.before ?? '',
          after: payload.deliveryInfo.after ?? '',
          changeover: payload.deliveryInfo.changeover ?? null,
        };
      }
      if (payload.lunchBreak) {
        mockStore.metrics.status.operations.lunchBreak = {
          start: payload.lunchBreak.start ?? null,
          end: payload.lunchBreak.end ?? null,
        };
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'queryLimit')) {
        mockStore.metrics.status.operations.queryLimit = payload.queryLimit ?? null;
      }
      if (payload.deliveryInfo) {
        mockStore.metrics.status.operations.delivery = {
          before: payload.deliveryInfo.before ?? '',
          after: payload.deliveryInfo.after ?? '',
          changeover: payload.deliveryInfo.changeover ?? null,
        };
      }
      const touched = [];
      if (payload.timezone || payload.weekly) touched.push('ساعات کاری');
      if (payload.platforms) touched.push('پلتفرم‌ها');
      if (payload.lunchBreak) touched.push('استراحت ناهار');
      if (Object.prototype.hasOwnProperty.call(payload, 'queryLimit'))
        touched.push('محدودیت استعلام');
      if (payload.deliveryInfo) touched.push('اطلاعات تحویل');
      if (touched.length) {
        const summary = [...new Set(touched)].join('، ');
        pushMockAudit('به‌روزرسانی تنظیمات', summary);
      }
      return mockStore.settings;
    };

    const result = await runWithFallback(
      'updateSettings',
      () => request('/api/v1/settings', { method: 'PUT', body: payload }),
      mockHandler
    );
    if (isMockMode() || result?.dataSource === 'fallback') {
      emitFallback({ method: 'updateSettings', reason: 'usingFallback' });
    }
    return result;
  },

  async toggleBot(active) {
    const mockHandler = () => {
      mockStore.metrics.status.active = active;
      mockStore.metrics.status.message = active
        ? 'ربات فعال و آماده پاسخ‌گویی است.'
        : 'ربات غیرفعال است.';
      pushMockAudit('تغییر وضعیت ربات', active ? 'فعال' : 'غیرفعال');
      return mockStore.metrics.status;
    };

    return runWithFallback(
      'toggleBot',
      () => request('/api/v1/bot/toggle', { method: 'POST', body: { active } }),
      mockHandler
    );
  },

  async invalidateCache() {
    const mockHandler = () => {
      const now = new Date().toISOString();
      mockStore.metrics.cache.lastUpdatedISO = now;
      pushMockAudit('به‌روزرسانی کش کالا', now);
      return { lastUpdatedISO: now };
    };

    return runWithFallback(
      'invalidateCache',
      () => request('/api/v1/cache/invalidate', { method: 'POST' }),
      mockHandler
    );
  },

  async getAuditLog({ page = 1, pageSize = 20 } = {}) {
    const parsedPage = Number(page);
    const parsedSize = Number(pageSize);
    const safePage = Number.isFinite(parsedPage) && parsedPage > 0 ? Math.floor(parsedPage) : 1;
    const safeSize = Number.isFinite(parsedSize) && parsedSize > 0 ? Math.floor(parsedSize) : 20;
    const params = new URLSearchParams({
      page: String(safePage),
      pageSize: String(safeSize),
    });

    const result = await runWithFallback(
      'getAuditLog',
      () => request(`/api/v1/audit-log?${params.toString()}`),
      () => {
        const total = mockStore.auditLog.length;
        const totalPages = Math.max(1, Math.ceil(total / safeSize));
        const currentPage = Math.min(safePage, totalPages);
        const start = (currentPage - 1) * safeSize;
        const items = mockStore.auditLog.slice(start, start + safeSize);
        return {
          items,
          total,
          page: currentPage,
          pageSize: safeSize,
          pages: totalPages,
          dataSource: 'fallback',
        };
      }
    );
    if (isMockMode() || result?.dataSource === 'fallback') {
      emitFallback({ method: 'getAuditLog', reason: 'usingFallback' });
    }
    return result;
  },

  async getPrivateTelegramSettings() {
    return runWithFallback(
      'getPrivateTelegramSettings',
      () => request('/api/v1/private-telegram/settings'),
      () => mockStore.privateTelegram
    );
  },

  async updatePrivateTelegramSettings(payload) {
    const mockHandler = () => {
      const current = mockStore.privateTelegram;
      const next = {
        ...current,
        ...payload,
      };
      if (Object.prototype.hasOwnProperty.call(payload, 'workingHours')) {
        next.workingHours = {
          start: payload.workingHours.start ?? '',
          end: payload.workingHours.end ?? '',
        };
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'thursdayHours')) {
        next.thursdayHours = {
          start: payload.thursdayHours.start ?? '',
          end: payload.thursdayHours.end ?? '',
        };
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'lunchBreak')) {
        next.lunchBreak = {
          start: payload.lunchBreak.start ?? '',
          end: payload.lunchBreak.end ?? '',
        };
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'deliveryInfo')) {
        next.deliveryInfo = {
          before15: payload.deliveryInfo.before15 ?? '',
          after15: payload.deliveryInfo.after15 ?? '',
        };
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'adminGroupIds')) {
        next.adminGroupIds = [...(payload.adminGroupIds ?? [])];
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'secondaryGroupIds')) {
        next.secondaryGroupIds = [...(payload.secondaryGroupIds ?? [])];
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'blacklist')) {
        next.blacklist = [...(payload.blacklist ?? [])];
      }
      const touched = [];
      if (Object.prototype.hasOwnProperty.call(payload, 'enabled')) touched.push('وضعیت');
      if (Object.prototype.hasOwnProperty.call(payload, 'dmEnabled')) touched.push('پیام خصوصی');
      if (
        Object.prototype.hasOwnProperty.call(payload, 'apiId') ||
        Object.prototype.hasOwnProperty.call(payload, 'apiHash') ||
        Object.prototype.hasOwnProperty.call(payload, 'phoneNumber')
      ) {
        touched.push('احراز هویت');
      }
      if (
        Object.prototype.hasOwnProperty.call(payload, 'dataSource') ||
        Object.prototype.hasOwnProperty.call(payload, 'excelFile')
      ) {
        touched.push('منبع داده');
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'cacheDurationMinutes'))
        touched.push('کش');
      if (
        Object.prototype.hasOwnProperty.call(payload, 'mainGroupId') ||
        Object.prototype.hasOwnProperty.call(payload, 'newGroupId') ||
        Object.prototype.hasOwnProperty.call(payload, 'adminGroupIds')
      )
        touched.push('گروه‌ها');
      if (
        Object.prototype.hasOwnProperty.call(payload, 'workingHours') ||
        Object.prototype.hasOwnProperty.call(payload, 'thursdayHours') ||
        Object.prototype.hasOwnProperty.call(payload, 'disableFriday')
      )
        touched.push('ساعات کاری');
      if (Object.prototype.hasOwnProperty.call(payload, 'lunchBreak')) touched.push('ناهار');
      if (Object.prototype.hasOwnProperty.call(payload, 'queryLimit')) touched.push('محدودیت');
      if (
        Object.prototype.hasOwnProperty.call(payload, 'deliveryInfo') ||
        Object.prototype.hasOwnProperty.call(payload, 'changeoverHour')
      ) {
        touched.push('پیام تحویل');
      }
      if (Object.prototype.hasOwnProperty.call(payload, 'blacklist')) {
        touched.push('لیست سیاه خصوصی');
      }
      mockStore.privateTelegram = next;
      if (touched.length) {
        const summary = [...new Set(touched)].join('، ');
        pushMockAudit('به‌روزرسانی تنظیمات تلگرام خصوصی', summary);
      }
      return next;
    };

    return runWithFallback(
      'updatePrivateTelegramSettings',
      () => request('/api/v1/private-telegram/settings', { method: 'PUT', body: payload }),
      mockHandler
    );
  },
};
