# FreeMoney Backend Foundation (MVP)

Backend foundation for a Telegram shop bot MVP.

## What is implemented

- Clean modular structure (`app/core`, `app/db`, `app/models`, `app/services`, `tests`, `alembic`).
- Configuration via `pydantic-settings`.
- SQLAlchemy setup for SQLite-first development.
- Models:
  - `users`
  - `categories` (with subcategories through self-reference)
  - `products_pool` (1 row = 1 issued item)
  - `reservations`
  - `orders`
  - `payments`
  - `user_category_prices`
  - `activity_logs` (for reservation/payment/sale/delivery events)
- Status enums for business workflows.
- Reservation/purchase service foundation:
  - reserve one available item in category with retry across candidates on conflict
  - create reservation with TTL and linked order
  - release expired reservations and cancel pending orders
  - apply payment success/failure transitions consistently
  - complete auto-delivery by storing delivered payload and marking order delivered
- Telegram bot foundation with modular aiogram routers:
  - bot polling entrypoint
  - `/start` user initialization flow
  - RU/EN text helper and main menu keyboard
  - profile and orders handlers backed by database data
  - placeholder handlers for Products / Top Up / Rules / Support
- Alembic migration scaffolding + initial migration.
- Tests for reservation and payment flows plus user service checks.

## Schema changes and rationale

1. Money fields now use `Numeric(12,2)` / `Decimal` (`users.balance`, `orders.price`, `payments.amount`, `user_category_prices.price`) to avoid floating-point rounding issues in financial logic.
2. `orders` now has `reservation_id` (unique FK) to explicitly bind each order to reservation flow.
3. Reservation expiry flow updates related order status to `canceled` when still pending.
4. Removed unique constraint from `orders.product_id` so one product can appear in multiple historical orders (e.g., failed payment then later successful purchase); unique constraint on `orders.reservation_id` is kept.
5. Added delivery fields to `orders`: `delivered_payload` and `delivered_at` to persist auto-delivery result and completion timestamp.
6. Payment success now follows paid->delivered completion flow with `DELIVERY_COMPLETED` log; failed/expired payments consistently cancel reservation/order and release product back to `available`.

## Project structure

```text
app/
  bot/
    handlers/
      menu.py
      start.py
    keyboards/
      main_menu.py
    i18n.py
    main.py
    router.py
  core/
    config.py
  db/
    base.py
    session.py
  models/
    *.py
  services/
    purchase.py
    reservations.py
    payments.py
    orders.py
    users.py
  main.py
alembic/
  env.py
  versions/
    0001_initial_schema.py
tests/
  test_models_and_services.py
  test_user_services.py
```

## Quick start

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 2) Configure environment (optional)

Defaults are development-friendly; override with `.env`:

```env
DATABASE_URL=sqlite:///./freemoney.db
TELEGRAM_BOT_TOKEN=your_bot_token_here
BLOCKCHAIN_EXPLORER_BASE_URLS={"bsc":"https://api.bscscan.com/api"}
BLOCKCHAIN_EXPLORER_API_KEYS={"bsc":"your_bscscan_api_key"}
BLOCKCHAIN_AMOUNT_TOLERANCE=0
BLOCKCHAIN_SUPPORTED_CRYPTO_OPTIONS={"bsc_usdt":{"network":"bsc","display_label":"USDT BSC (BEP20)","token_symbol":"usdt","token_contract":"0x55d398326f99059ff775485246999027b3197955","token_decimals":18,"recipient_wallet":"0xyour_deposit_wallet","is_native_coin":false}}
ACTIVATION_API_BASE_URL=http://127.0.0.1:9000
ACTIVATION_API_TIMEOUT_SECONDS=10
```

### 3) Run migrations

```bash
alembic upgrade head
```

### 4) Run API skeleton

```bash
uvicorn app.main:app --reload
```

Health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

### 5) Run Telegram bot polling

```bash
python -m app.bot.main
```

This starts aiogram polling with routers from `app/bot/router.py`.

### 6) Run tests

```bash
pytest
```


## Activation website (MVP product page)

A dedicated activation website is now included as a minimal user-facing page (not a full store).

- URL: `http://127.0.0.1:8000/activation`
- Root (`/`) redirects to `/activation`
- UI includes RU/EN toggle, polished activation form, validation, loading state, and result card

### Activation flow

The website orchestrates the existing activation API flow in this strict order:

1. `check_cdk`
2. `check_token`
3. `create_task`
4. `check_task`

Displayed status transitions:

- checking code
- checking token
- creating activation
- activation in progress
- activation success / failed

### How this relates to Telegram bot

The Telegram bot remains the primary shop/sales surface.
The website is a companion activation-only experience where a user pastes code/token received from the Telegram flow and completes activation.

### Running locally

1. Start backend app:

```bash
uvicorn app.main:app --reload
```

2. Open:

```text
http://127.0.0.1:8000/activation
```

3. Ensure `ACTIVATION_API_BASE_URL` points to the activation API service that supports:

- `POST /check_cdk`
- `POST /check_token`
- `POST /create_task`
- `POST /check_task`

## Notes on business rules coverage

- Product statuses: `available`, `reserved`, `sold`.
- Expired reservations are released by `release_expired_reservations()`.
- Failed/expired payments return products to `available` via `apply_payment_status()`.
- Sales/reservations/payment failures are logged in `activity_logs`.

## Crypto TXID verification flow (real on-chain check)

- Scope implemented now: `CRYPTO_TXID` request verification on EVM-compatible chains, with BSC configured first.
- On `verify_crypto_txid_top_up(..., target_status=VERIFIED)`:
  1. Existing safe status checks run first (method, status transition, duplicate credit guard).
  2. Service requests transaction + receipt from configured explorer API (BscScan-compatible proxy endpoints).
  3. Verification requires:
     - tx exists,
     - tx receipt status is successful (`0x1`),
     - network + token match a configured supported crypto option,
     - recipient wallet matches the option's `recipient_wallet`,
     - for token transfers, receipt log contract address matches option `token_contract`,
     - for token transfers, amount is decoded with option `token_decimals`,
     - amount is at least requested amount (plus optional tolerance).
  4. Only then request becomes `VERIFIED`, user balance is credited once, and verified on-chain fields are persisted.
- On-chain verification failures keep the request safe (not credited, no terminal status transition) and store a verification note with failure reason.

### Supported crypto options config

- `BLOCKCHAIN_SUPPORTED_CRYPTO_OPTIONS` is the source of truth for supported deposits.
- Each option must include:
  - `network` (e.g. `bsc`)
  - `display_label` (shown to user in bot)
  - `token_symbol` (`usdt` for token flow, null for native coin flow)
  - `token_contract` (required for token flow)
  - `token_decimals`
  - `recipient_wallet`
  - `is_native_coin` (`false` for BSC USDT BEP20)
- For BSC USDT verification specifically, configure real BEP20 USDT contract and your deposit wallet in this option.
