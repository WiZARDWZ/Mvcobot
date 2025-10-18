# Mvcobot

Mvcobot is a Telegram automation bot that integrates with Sepidar databases to answer inventory and delivery queries. The project now ships with a bundled web-based control panel that exposes live metrics, settings, and manual overrides for operators.

## Features

- Telegram bot built with `python-telegram-bot` and resilient polling with automatic retry logic.
- SQL Server integrations for both Sepidar (source of truth) and the bot cache database.
- Centralised settings such as lunch breaks, delivery messaging, and per-user query limits.
- WebControl dashboard served from `webControl/` for monitoring command history, cache health, blocklists, and manual command management.
- Automatic startup of the control panel HTTP server when `bot.py` runs so operations can be managed from the browser.

## Project Structure

```
├── bot.py                # Application entry-point that also hosts the control panel
├── config.py             # Database credentials and third-party API configuration
├── control_panel/        # HTTP server, API handlers, and business logic for the dashboard
├── database/             # Database helper modules for Sepidar and bot data
├── handlers/             # Telegram conversation handlers and command flows
├── utils/                # Shared helper utilities
├── wa/                   # WhatsApp related integrations
└── webControl/           # Static assets for the control panel single-page app
```

## Prerequisites

- Python 3.10 or newer
- Access to Microsoft SQL Server with the schemas required by `Sepidar01` and `MvcobotDB`
- [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) installed on the host
- Recommended: a Python virtual environment to isolate dependencies

## Installation

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   ```
2. Install Python dependencies:
   ```bash
   pip install python-telegram-bot==20.* pyodbc requests playwright
   playwright install
   ```
3. Update `config.py` with the correct database credentials and bot token for your environment. Never commit production secrets to source control.

## Running the Bot and Control Panel

1. Ensure the databases referenced in `config.py` are reachable from the host.
2. (Optional) Configure the control panel port:
   ```bash
   export CONTROL_PANEL_PORT=8080  # Windows PowerShell: $env:CONTROL_PANEL_PORT = "8080"
   ```
3. Start the bot:
   ```bash
   python bot.py
   ```
4. Open the control panel in your browser at `http://localhost:8080` (replace the port if you changed it). The dashboard shows live stats, settings, and provides tools for command management and cache control.

When the application cannot reach the configured databases, it automatically switches to sample data so you can still demonstrate the UI. In this mode, a warning banner appears at the top of the dashboard reminding you that the data is not live.

## Packaging with PyInstaller

To create a single-file executable that bundles the Telegram bot, control panel API, and static assets, run the following command (PowerShell / CMD):

```bash
pyinstaller -F -n mvco90_stable --paths . \
  --collect-all telegram \
  --collect-all playwright \
  --collect-submodules playwright \
  --collect-submodules control_panel \
  --hidden-import playwright.async_api \
  --hidden-import playwright.sync_api \
  --add-data "webControl;webControl" \
  bot.py
```

> **Tip:** On Linux or macOS replace the semicolon in the `--add-data` flag with a colon: `--add-data "webControl:webControl"`.

The generated binary appears in the `dist/` directory as `mvco90_stable`. Distribute this file together with the Playwright browser dependencies that were installed via `playwright install`.

## Troubleshooting

- **Control panel does not start:** Ensure the selected port is free and that the process has permission to bind to it. Logs are printed to stdout alongside the bot logs.
- **Database errors:** Validate connectivity with the configured SQL Server instances. When credentials are wrong the bot falls back to cached data and the control panel shows the mock data warning.
- **Telegram `Conflict` errors:** Only run one instance of the bot at a time. Stop other deployments before starting a new one.

## Contributing

1. Create a feature branch.
2. Make your changes and run linting/tests as appropriate.
3. Commit with a descriptive message and open a pull request summarising the work and how to test it.

For operational questions or escalations, contact the DevOps owner of the Sepidar infrastructure.
