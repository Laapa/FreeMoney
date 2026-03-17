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
- Alembic migration scaffolding + initial migration.
- Tests for reservation and payment flows.

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
  main.py
alembic/
  env.py
  versions/
    0001_initial_schema.py
tests/
  test_models_and_services.py
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

### 5) Run tests

```bash
pytest
```

## Notes on business rules coverage

- Product statuses: `available`, `reserved`, `sold`.
- Expired reservations are released by `release_expired_reservations()`.
- Failed/expired payments return products to `available` via `apply_payment_status()`.
- Sales/reservations/payment failures are logged in `activity_logs`.

