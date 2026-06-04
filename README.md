# HdRezka DB Filter

Локальная страница поиска по собственной PostgreSQL-базе фильмов. Обычный поиск не делает live-запросы к Rezka или IMDb: данные сначала должны быть загружены в БД.

## Возможности

- пользователи `test1` и `test2`;
- отдельные состояния фильмов для каждого пользователя: `seen`, `hidden`, `favorite`, `watchlist`;
- история показанных результатов по `user_id + query_hash`;
- фильтры жанров и стран на включение;
- бан-листы жанров и стран;
- фильтр IMDb min/max;
- сортировка IMDb от высокой или от низкой;
- режим карточек и текстовый режим;
- локальные seed/reset/test скрипты без сетевых запросов.

## Установка

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pip install -r requirements.txt
```

## База

```powershell
$env:DATABASE_URL = "postgresql://hdrezka_user:password@localhost:5432/hdrezka_filter"
psql $env:DATABASE_URL -f migrations/001_init.sql
```

Тестовые данные:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/seed_test_data.py
```

Сброс тестовых фильмов и пользовательских состояний:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/reset_test_db.py
```

## Запуск

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" main.py
```

Открыть:

```text
http://127.0.0.1:8000/
```

Debug:

```powershell
$env:HDREZKA_DEBUG = "1"
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" main.py
```

## Остановка сервера

Через интерфейс: кнопка `Остановить сервер`.

Через PowerShell:

```powershell
.\stop_server.ps1
```

## Проверки

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m py_compile main.py app/**/*.py tests_local/*.py
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/test_search_logic.py
```

`test_search_logic.py` требует поднятый PostgreSQL и примененную миграцию.

## Структура

```text
app/
  clients/              # Rezka/IMDb clients for future crawler work
  repositories/         # SQL repository layer
  services/             # search, state, query hash
  utils/
  config.py
  database.py
  server.py
migrations/
  001_init.sql
static/
  app.js
  styles.css
templates/
  index.html
tests_local/
main.py
requirements.txt
```

Подробный статус и дальнейшие этапы: [PROJECT_STATUS.md](PROJECT_STATUS.md).
