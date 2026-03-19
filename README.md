# FreeMoney MVP Backend (Bot + Activation Site)

This repository contains the MVP backend for:
- Telegram bot shop flow (catalog, reservation, top-up request creation).
- Activation website (`/activation`) for final code/token activation.

## 1) Environment and configuration

Copy example environment and edit values:

```bash
cp .env.example .env
```

### Required variables

- `DATABASE_URL` - database connection string.
- `TELEGRAM_BOT_TOKEN` - required to run the Telegram bot.
- `ACTIVATION_API_BASE_URL` - external activation API base URL.

### Important optional variables

- `LOG_LEVEL` (`INFO` by default).
- `SQL_ECHO` (`false` by default).
- `ACTIVATION_API_TIMEOUT_SECONDS`.
- `BLOCKCHAIN_EXPLORER_BASE_URLS` / `BLOCKCHAIN_EXPLORER_API_KEYS`.
- `BLOCKCHAIN_SUPPORTED_CRYPTO_OPTIONS`.
- `BLOCKCHAIN_AMOUNT_TOLERANCE`.

All environment variables are documented in `.env.example`.

## 2) Local setup (step-by-step)

### Step A - install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### Step B - run database migrations

```bash
alembic upgrade head
```

### Step C - optional development seed (demo-only)

```bash
freemoney-seed-demo
```

This inserts development demo data (categories/products/demo user). Do not use in production.

Demo seed specifics (for local manual catalog testing):
- Categories: `Games` root + `Steam` and `Xbox` subcategories.
- Products: demo keys in `Steam` and `Xbox` with `AVAILABLE` status.
- Demo pricing rows in `user_category_prices` for `Steam` and `Xbox`.
- Catalog price resolution first tries the current Telegram user's personal row, then falls back to the seeded category price if user-specific pricing is missing.

### Step C.1 - optional: credit balance for your own Telegram test user

If you test with your own Telegram account (not the seeded demo user), use:

```bash
freemoney-credit-balance
```

The helper prompts for:
- Telegram ID
- amount to credit

It updates the existing user balance in DB and prints the new balance, so manual purchase smoke-tests do not require direct SQL edits.

### Step D - run API / website

```bash
uvicorn app.main:app --reload
```

Open:
- Activation page: `http://127.0.0.1:8000/activation`
- API health: `http://127.0.0.1:8000/health`
- API readiness (DB check): `http://127.0.0.1:8000/health/ready`

### Step E - run Telegram bot

```bash
python -m app.bot.main
```

### Step F - run tests

```bash
pytest
```

## 3) Command reference (separated)

- **Bot run command**: `python -m app.bot.main`
- **Website/API run command**: `uvicorn app.main:app --reload`
- **Migration command**: `alembic upgrade head`
- **Test command**: `pytest`
- **Dev seed command**: `freemoney-seed-demo`
- **Dev balance credit command**: `freemoney-credit-balance`

## 4) Smoke-test checklist

After setup, verify:

1. Bot starts without crash (`python -m app.bot.main`).
2. Website/API starts (`uvicorn app.main:app --reload`).
3. Migrations apply cleanly (`alembic upgrade head`).
4. Category browsing works in Telegram bot.
5. Reservation works in Telegram bot and creates reservation/order.
6. Top-up request creation works (crypto and/or bybit path).
7. Activation page opens and validates invalid token JSON input.
8. Activation submit calls backend flow and returns success/pending/failed state.
9. Health endpoints return OK (`/health`, `/health/ready`).
10. Purchase E2E flow in bot:
   - reserve product in catalog,
   - open order in Orders,
   - pay from balance,
   - verify payload is delivered and order status becomes `delivered`.

## 5) Logging and error visibility

- Logging is centralized via `LOG_LEVEL` and structured message format.
- Important MVP flows now emit practical logs:
  - reservation creation/conflicts/payment outcome,
  - top-up creation and verification,
  - activation result transitions.
- User-facing responses remain safe and do not expose internal exceptions.

## 6) Docker (minimal MVP deploy option)

### Build and run with docker compose

```bash
docker compose up --build
```

This starts:
- `db` (PostgreSQL 16)
- `app` (FastAPI app, auto-runs `alembic upgrade head` before start)

Then open `http://127.0.0.1:8000/activation`.

## 7) Production readiness notes (initial MVP)

Before first real production launch:
- Replace all placeholder secrets and wallet addresses in `.env`.
- Use managed Postgres and secure network rules.
- Set `APP_ENV=prod`, `LOG_LEVEL=INFO` (or `WARNING`).
- Keep demo seed disabled in production operations.
- Confirm real activation API contract and timeout behavior.
- Perform full smoke checklist in a staging environment.

## 8) What this change set intentionally does NOT do

- No major product-feature expansion.
- No heavy infrastructure orchestration.
- No aggressive architecture refactor.

Focus is MVP stability, clarity, safe configuration, and deployment readiness.
