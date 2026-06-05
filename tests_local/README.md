# Local DB MVP tests

PostgreSQL is required. Normal search uses only the local database.

## Environment

```bash
cp .env.example .env
export DATABASE_URL="postgresql://hdrezka_user:password@localhost:5432/hdrezka_filter"
export HDREZKA_DEBUG=1
export REZKA_BASE_URL="https://rezka.ag/"
```

For live crawler checks, keep `REZKA_COOKIE` in local `.env` fresh from browser
DevTools -> Network -> Copy as cURL. Do not commit real cookies.

## Apply migration

```bash
psql "$DATABASE_URL" -f migrations/001_init.sql
```

## Seed/reset without network

```bash
.venv/bin/python tests_local/reset_test_db.py
.venv/bin/python tests_local/seed_test_data.py
```

## Run SQL checks

```bash
.venv/bin/python tests_local/test_search_logic.py
```

## Run site

```bash
.venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```
