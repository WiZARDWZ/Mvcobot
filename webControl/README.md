# Mvcobot Control Panel

پنل مدیریت فرانت‌اند برای ربات Mvcobot که به صورت Single-Page Application پیاده‌سازی شده و آماده اتصال به API واقعی است.

## راه‌اندازی محلی

1. مخزن را کلون کنید و به پوشه پروژه وارد شوید.
2. یک وب‌سرور ساده اجرا کنید (به عنوان مثال):
   ```bash
   npx serve .
   # یا
   python -m http.server 5173
   ```
3. فایل `index.html` را در مرورگر باز کنید.

> **نکته:** از اجرای مستقیم فایل HTML با مسیر `file://` خودداری کنید؛ زیرا ماژول‌های ES6 نیاز به سرو شدن از طریق HTTP دارند.

## پیکربندی

در فایل `index.html` شیء سراسری `window.APP_CONFIG` تعریف شده است. با مقداردهی `API_BASE_URL` می‌توانید کنترل پنل را به سرور واقعی متصل کنید. در غیر این صورت داده‌های Mock داخلی مورد استفاده قرار می‌گیرند.

اگر اتصال به سرور برقرار نشود (مثلاً سرور در دسترس نباشد) برنامه به صورت خودکار با نمایش هشدار به داده‌های Mock بازمی‌گردد تا رابط کاربری همچنان قابل استفاده بماند.

```js
window.APP_CONFIG = {
  API_BASE_URL: '',
  API_KEY: '',
  TELEGRAM_ENABLED: true,
  WHATSAPP_ENABLED: true,
};
```

## توسعه و Lint

وابستگی‌های توسعه را نصب کنید:

```bash
npm install
```

سپس برای بررسی کد از ESLint و Prettier استفاده کنید:

```bash
npm run lint
npm run format
```

برای فرمت خودکار:

```bash
npm run format:write
```

## ساختار پوشه‌ها

```
assets/
  css/
    styles.css
  js/
    api.js
    router.js
    ui/
      components.js
      dashboard.js
      commands.js
      blocklist.js
      settings.js
index.html
```

هر تب رابط کاربری یک ماژول مستقل دارد و `router.js` به صورت Lazy Load آن‌ها را وارد می‌کند. ماژول `api.js` بسته به مقداردهی `APP_CONFIG` بین Mock و API واقعی جابه‌جا می‌شود.
