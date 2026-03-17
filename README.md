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
- Alembic migration scaffolding + initial migration.
- Minimal tests with `pytest` for core reservation/payment behavior.

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

