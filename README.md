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
- Product reservation/order creation with fulfillment types:
  - `direct_stock` (instant payload delivery),
  - `activation_task` (paid -> processing activation task),
  - `manual_supplier` (paid -> manual/supplier processing).
- Order listing/details.
- Parallel payment flows:
  - Crypto Pay real invoices (`provider=crypto_pay`) when `CRYPTOPAY_API_TOKEN` is configured,
  - test stub flow (`provider=test_stub`) when Crypto Pay token is not configured.
- Top-up request flows:
  - crypto (TXID-based verification),
  - Bybit UID / external reference flow (reviewed by operator/manual process).

### Activation website features
- `/activation` page with RU/EN UI toggle.
- CDK + token JSON form validation.
- Activation flow result UI (success/pending/failed) with step-by-step output.

### Data and operations
- SQLAlchemy models and Alembic migrations.
- Dev seed script for demo catalog/test data.
- CLI helper to credit a Telegram user balance locally for test payments.

---

## 2) SQLite-first quick start (local happy path)

SQLite is the primary and recommended local/runtime database for WEBSTER-SHOP.

### Prerequisites
- Python 3.11+

### Step A — create and activate virtual environment

#### Linux/macOS
```bash
python -m venv .venv
source .venv/bin/activate
```

#### Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step B — install project
```bash
pip install -e .
```

Optional (for running tests):
```bash
pip install -e .[dev]
```

### Step C — configure environment
```bash
cp .env.example .env
```

`DATABASE_URL` should stay on SQLite for the default path:
```env
DATABASE_URL=sqlite:///./webster_shop.db
```

### Step D — run migrations
```bash
alembic upgrade head
```

### Step E — seed demo data (dev only)
```bash
python -m app.scripts.seed_demo_data
```

### Step F — run API + activation website
```bash
uvicorn app.main:app --reload
```
Open:
- Activation website: `http://127.0.0.1:8000/activation`
- Health: `http://127.0.0.1:8000/health`
- Readiness (DB ping): `http://127.0.0.1:8000/health/ready`

### Step G — run Telegram bot
```bash
python -m app.bot.main
```

### Step H — run tests
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
- Credit test balance helper: `python -m app.scripts.credit_balance`

---

## 4) Local top-up flow expectations

### Crypto by TXID
- User creates top-up request with amount + network/token.
- User submits TXID.
- Request moves to verification queue/status.
- TXID verification can be completed by project verification service/operators depending on environment setup.

### Bybit UID / external reference
- User creates top-up request with amount.
- User submits Bybit sender UID or external transfer reference.
- Request is queued for operator/manual review.
- Do not assume automatic Bybit verification unless your deployment explicitly implements it.

---

## 5) How to credit balance locally for testing payments

Use:
```bash
python -m app.scripts.credit_balance
```

The script prompts for:
- Telegram user ID
- amount

It updates the existing user balance and prints the new total.

---

## 6) Environment variables

## Required
- `DATABASE_URL` — database DSN (SQLite is default/recommended for local/runtime).
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
- `CRYPTOPAY_API_TOKEN` (enables real Crypto Pay invoice payments in orders)
- `CRYPTOPAY_USE_TESTNET` (default `false`)
- `CRYPTOPAY_API_BASE_URL` (optional override; default resolved by testnet flag)
- `CRYPTOPAY_ASSET` (default `USDT`)
- `CRYPTOPAY_INVOICE_EXPIRES_IN` in seconds (default `1800`)

See `.env.example` for a complete template.

### Crypto Pay quick note
- Press **Pay** in order details to create payment.
- For Crypto Pay invoices, bot shows **Proceed to payment** URL button + **Check payment** button.
- When invoice status becomes `paid`, existing fulfillment flow runs as-is:
  - `direct_stock` -> immediate delivery,
  - `activation_task` -> processing + activation path,
  - `manual_supplier` -> processing.

---

## 7) Optional: PostgreSQL and Docker for compatibility checks

SQLite is the primary setup for this project.

If you specifically need PostgreSQL compatibility testing, you can use the provided `docker-compose.yml` and switch `DATABASE_URL` to a PostgreSQL DSN. This is optional and not required for the normal local runtime workflow.

---

## 8) External services and dependencies

The following parts depend on external integrations:
- Telegram Bot API (`TELEGRAM_BOT_TOKEN`) for bot operation.
- Activation service API (`ACTIVATION_API_BASE_URL`) for `/activation` flow completion.
- Blockchain explorer API(s) for TXID verification in crypto top-up checks.

If these are unavailable/misconfigured, related flows will degrade or fail.

---

## 9) Handoff summary (client-facing)

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
- User can create and test-confirm order payments in bot UX without real external money movement.

### Known external dependency
- Activation service is external and must satisfy expected request/response contract.

### Production notes
- Replace all placeholder secrets and wallet addresses.
- Keep demo seed scripts disabled in production routines.
- Validate activation API behavior and timeout values in staging.
- Run smoke test checklist before release.

---

## 10) Delivery smoke-test checklist

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

## 11) Intentional constraints of this delivery pass

- No new major product features.
- No risky architecture refactors.
- Focus on stability, clarity, branding consistency, and handoff readiness.
