# WEBSTER-SHOP MVP Backend (Telegram Bot + Activation Website)

WEBSTER-SHOP is an MVP backend that includes:
- a Telegram shop bot (catalog browsing, reservation, order payment from balance, top-up request flows),
- an activation website (`/activation`) for final account/product activation,
- supporting API endpoints, database models, and migrations.

This document is written for client handoff and developer onboarding.

## 1) What the project includes

### Telegram bot features
- Language selection (RU/EN) on first start.
- Main menu: products, top-up, profile, orders, rules/support placeholders.
- Product catalog navigation by category.
- Product reservation with order creation.
- Order listing/details.
- Balance payment and payload delivery flow.
- Top-up request flows:
  - crypto (TXID-based verification),
  - Bybit UID / external reference flow.

### Activation website features
- `/activation` page with RU/EN UI toggle.
- CDK + token JSON form validation.
- Activation flow result UI (success/pending/failed) with step-by-step output.

### Data and operations
- SQLAlchemy models and Alembic migrations.
- Dev seed script for demo catalog/test data.
- CLI helper to credit a Telegram user balance locally for test payments.

---

## 2) Quick start (local)

### Prerequisites
- Python 3.11+
- PostgreSQL (optional; SQLite works for basic local tests)

### Step A — install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### Step B — configure environment
```bash
cp .env.example .env
```
Fill required values in `.env`.

### Step C — run migrations
```bash
alembic upgrade head
```

### Step D — optional demo seed data (dev only)
```bash
python -m app.scripts.seed_demo_data
```
This creates demo categories/products/pricing for manual bot checks.

### Step E — run API + activation website
```bash
uvicorn app.main:app --reload
```
Open:
- Activation website: `http://127.0.0.1:8000/activation`
- Health: `http://127.0.0.1:8000/health`
- Readiness (DB ping): `http://127.0.0.1:8000/health/ready`

### Step F — run Telegram bot
```bash
python -m app.bot.main
```

### Step G — run tests
```bash
pytest
```

---

## 3) Commands reference

- Run API/website: `uvicorn app.main:app --reload`
- Run Telegram bot: `python -m app.bot.main`
- Apply migrations: `alembic upgrade head`
- Run tests: `pytest`
- Seed demo data: `python -m app.scripts.seed_demo_data`
- Credit test balance: `python -m app.scripts.credit_balance`

---

## 4) How to credit balance locally for testing

Use:
```bash
python -m app.scripts.credit_balance
```
The script prompts for:
- Telegram user ID
- amount

It updates the existing user balance and prints the new total.

---

## 5) Environment variables

## Required
- `DATABASE_URL` — database DSN.
- `TELEGRAM_BOT_TOKEN` — required for Telegram bot runtime.
- `ACTIVATION_API_BASE_URL` — external activation API base URL.

## Important optional
- `APP_NAME`, `APP_ENV`, `LOG_LEVEL`
- `SQL_ECHO`
- `ACTIVATION_API_TIMEOUT_SECONDS`
- `BLOCKCHAIN_EXPLORER_BASE_URLS`
- `BLOCKCHAIN_EXPLORER_API_KEYS`
- `BLOCKCHAIN_SUPPORTED_CRYPTO_OPTIONS`
- `BLOCKCHAIN_AMOUNT_TOLERANCE`

See `.env.example` for a complete template.

---

## 6) External services and dependencies

The following parts depend on external integrations:
- Telegram Bot API (`TELEGRAM_BOT_TOKEN`) for bot operation.
- Activation service API (`ACTIVATION_API_BASE_URL`) for `/activation` flow completion.
- Blockchain explorer API(s) for TXID verification in crypto top-up checks.

If these are unavailable/misconfigured, related flows will degrade or fail.

---

## 7) Handoff summary (client-facing)

### Telegram bot MVP scope
- RU/EN onboarding
- catalog browsing + reservation
- orders list/details
- pay-from-balance and instant delivery payload
- top-up request creation and status tracking

### Activation website MVP scope
- user enters CDK + token JSON
- backend processes activation stages
- user sees clear status and step messages

### Top-up/payment flows
- User can top up via crypto TXID or Bybit UID/reference request.
- User can pay pending orders from balance once sufficient funds are available.

### Known external dependency
- Activation service is external and must satisfy expected request/response contract.

### Production notes
- Replace all placeholder secrets and wallet addresses.
- Use managed PostgreSQL and secure network rules.
- Keep demo seed scripts disabled in production routines.
- Validate activation API behavior and timeout values in staging.
- Run smoke test checklist before release.

---

## 8) Delivery smoke-test checklist

1. Bot starts without crash.
2. API/website starts and `/activation` loads.
3. Migrations apply cleanly.
4. Start + language selection works (RU/EN).
5. Catalog navigation and reservation work.
6. Orders can be opened and paid from balance.
7. Delivery payload is shown after successful payment.
8. Top-up request creation works for intended methods.
9. `/health` and `/health/ready` return OK.
10. Activation page validates invalid JSON and handles normal submission lifecycle.

---

## 9) Intentional constraints of this delivery pass

- No new major product features.
- No risky architecture refactors.
- Focus on stability, clarity, branding consistency, and handoff readiness.
