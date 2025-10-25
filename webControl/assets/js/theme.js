const STORAGE_KEY = 'mvcobot:theme';
const root = document.documentElement;
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

const toggleButton = document.querySelector('[data-theme-toggle]');
const iconSpan = toggleButton?.querySelector('[data-theme-icon]');
const labelSpan = toggleButton?.querySelector('[data-theme-label]');
const subtextSpan = toggleButton?.querySelector('[data-theme-subtext]');

function readStoredTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') {
      return stored;
    }
  } catch (error) {
    console.warn('Unable to read stored theme', error);
  }
  return null;
}

function persistTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (error) {
    console.warn('Unable to persist theme preference', error);
  }
}

function clearPersistedTheme() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.warn('Unable to clear theme preference', error);
  }
}

function resolveTheme(preferred) {
  if (preferred === 'light' || preferred === 'dark') {
    return preferred;
  }
  return prefersDark.matches ? 'dark' : 'light';
}

function updateToggleCopy(theme) {
  if (!toggleButton) return;
  const isDark = theme === 'dark';
  if (iconSpan) {
    iconSpan.textContent = isDark ? '🌞' : '🌙';
  }
  if (labelSpan) {
    labelSpan.textContent = isDark ? 'حالت روشن' : 'حالت تیره';
  }
  if (subtextSpan) {
    subtextSpan.textContent = isDark ? 'برای محیط‌های پرنور' : 'برای محیط‌های کم‌نور';
  }
  const nextModeText = isDark ? 'تغییر به حالت روشن' : 'تغییر به حالت تیره';
  toggleButton.setAttribute('aria-label', nextModeText);
  toggleButton.setAttribute('title', nextModeText);
}

function applyTheme(preferred) {
  const theme = resolveTheme(preferred);
  root.dataset.theme = theme;
  document.body?.setAttribute('data-theme', theme);
  updateToggleCopy(theme);
  return theme;
}

let storedTheme = readStoredTheme();
let activeTheme = applyTheme(storedTheme);

prefersDark.addEventListener('change', (event) => {
  storedTheme = readStoredTheme();
  if (storedTheme) {
    return;
  }
  activeTheme = applyTheme(event.matches ? 'dark' : 'light');
});

toggleButton?.addEventListener('click', () => {
  storedTheme = readStoredTheme();
  const currentTheme = storedTheme || activeTheme;
  const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
  persistTheme(nextTheme);
  activeTheme = applyTheme(nextTheme);
});

window.addEventListener('storage', (event) => {
  if (event.key !== STORAGE_KEY) {
    return;
  }
  storedTheme = readStoredTheme();
  if (!storedTheme) {
    clearPersistedTheme();
  }
  activeTheme = applyTheme(storedTheme);
});
