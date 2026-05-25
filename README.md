# Finance App

A personal finance tracker for macOS — a native desktop app built with Python and
[Flet](https://flet.dev). Track expenses, manage bills and subscriptions, visualize
spending, and log transactions on the go through an integrated Telegram bot.

> The user interface is in English. Source code comments are in Portuguese.

## Features

- **Dashboard & Home** — at-a-glance summary with Available balance, Bills due, and
  monthly Income cards.
- **Transaction history** — searchable, filterable list with inline category editing.
  Re-categorizing a transaction can optionally create a rule and apply it to similar past
  entries.
- **Bills & subscriptions** — track bills by due date. Mark recurring subscriptions that
  automatically regenerate for the next month once paid, or manually duplicate any bill to
  the following month.
- **Categories & rules** — customizable spending categories with user-defined
  "description → category" rules for automatic classification.
- **Analytics** — spending breakdowns by category and period (daily / weekly / monthly /
  yearly), with month-over-month comparisons.
- **CSV import** — import bank/credit-card statements (designed around Itaú and Nubank CSV
  formats), with automatic categorization and duplicate detection.
- **Telegram bot** — log expenses from your phone (e.g. `45.90 uber`). The bot starts with
  the app and stops when it closes. Only authorized Telegram user IDs can use it.

## Tech stack

- **Python 3.13**
- **Flet 0.28.3** — UI framework (Flutter-based) and desktop packaging
- **SQLAlchemy 2.x** + **SQLite** — data layer
- **bcrypt** — password hashing
- **python-telegram-bot** — Telegram integration
- **python-dateutil** — date handling

## Architecture

Layered design, separating UI from business logic from data:

```
src/
├── main.py              # Entry point (ft.app)
├── app/
│   ├── config.py        # Centralized settings & data paths
│   ├── auth/            # Password hashing / verification
│   ├── database/        # SQLAlchemy models, connection, migrations
│   ├── services/        # Business logic (transactions, bills, analytics, bot, ...)
│   └── ui/              # Views and reusable components
└── scripts/             # CLI helpers (init DB, import CSV, reset data)
```

- **Views** with state are classes; static views are functions.
- Money is handled with `Decimal` (never float).
- The database lives under the project's `data/` folder in development, and in the
  OS application-data directory when packaged.

## Getting started (development)

Requires Python 3.13.

```bash
# Clone and enter the project
git clone https://github.com/H4ykO/finance-app.git
cd finance-app

# Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env               # then edit .env with your values

# Run the app
cd src
python main.py
```

### Environment variables (`.env`)

| Variable                     | Description                                              |
|------------------------------|----------------------------------------------------------|
| `ADMIN_PASSWORD`             | Password used to create the initial admin account.       |
| `TELEGRAM_BOT_TOKEN`         | Telegram bot token from [@BotFather](https://t.me/BotFather) (optional). |
| `TELEGRAM_ALLOWED_USER_IDS`  | Comma-separated Telegram user IDs allowed to use the bot. |

The app runs fine without the Telegram variables — the bot simply stays off.

## Building the macOS app

With the dependencies installed and [Flutter](https://flutter.dev) + Xcode + CocoaPods
available:

```bash
flet build macos
```

The generated `.app` will be in `build/macos/`. Since it is unsigned, the first launch
requires right-click → **Open**.

## CSV import format

The importer expects three columns: `date,title,amount` (dates as `YYYY-MM-DD`). It follows
the Itaú convention where **positive = expense** and **negative = income/refund**. Imported
rows are de-duplicated by a hash of date + description + amount.

## License

[MIT](LICENSE) © 2026 H4ykO
