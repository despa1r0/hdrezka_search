# Local DB MVP tests

PostgreSQL is required. Normal search uses only the local database.

## Environment

```powershell
$env:DATABASE_URL = "postgresql://hdrezka_user:password@localhost:5432/hdrezka_filter"
$env:HDREZKA_DEBUG = "1"
```

## Apply migration

```powershell
psql $env:DATABASE_URL -f migrations/001_init.sql
```

## Seed/reset without network

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/reset_test_db.py
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/seed_test_data.py
```

## Run SQL checks

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/test_search_logic.py
```

## Run site

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/run_local.py
```

Open:

```text
http://127.0.0.1:8000/
```
