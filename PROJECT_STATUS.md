# HdRezka Filter: статус DB MVP

## Текущий вектор

Проект переводится с live-scraping поиска на локальную PostgreSQL-базу. Обычный пользовательский поиск больше не должен дергать Rezka или IMDb. Rezka/IMDb-клиенты остаются в репозитории для будущего crawler-этапа, но `/api/search` сейчас ищет только по таблице `movies`.

Текущий web-слой временно остается на `http.server`. FastAPI, Docker, VPS и Tailscale отложены до момента, когда DB MVP стабильно проходит локальные проверки.

## Что реализовано в этом этапе

- Восстановлен `main.py` как entrypoint через `app.server.run`.
- Добавлен PostgreSQL-слой:
  - `app/database.py` с `fetch_one`, `fetch_all`, `execute`, `execute_many`;
  - `migrations/001_init.sql` со схемой БД и seed-пользователями `test1`/`test2`;
  - `DATABASE_URL`, `HDREZKA_DEBUG` и crawler-лимиты читаются из env.
- Добавлены репозитории и сервисы:
  - пользователи;
  - фильмы, жанры и страны;
  - история показов `shown_items`;
  - состояния фильмов `seen`, `hidden`, `favorite`, `watchlist`;
  - стабильный `query_hash` без `limit`.
- Поиск переведен на SQL:
  - include жанров/стран работает как `AND`;
  - ban жанров/стран работает как `OR` exclusion через `NOT EXISTS`;
  - есть фильтры IMDb min/max, `content_type`, сортировка;
  - `seen` и `hidden` исключаются только для выбранного пользователя;
  - `favorite` и `watchlist` не исключают фильм из поиска;
  - повторный поиск может исключать уже показанные фильмы по `user_id + query_hash`.
- API текущего `http.server`:
  - `GET /api/users`;
  - `GET /api/search`;
  - `POST /api/movie-state`;
  - `POST /api/shutdown`.
- Frontend MVP:
  - выбор пользователя `test1`/`test2`;
  - поиск отправляет `user_id`;
  - карточки получают `movie_id`;
  - кнопки `Уже смотрел`, `Скрыть`, `В избранное`, `Хочу посмотреть`;
  - после `Уже смотрел`/`Скрыть` карточка убирается из текущей выдачи локально.
- Локальные инструменты:
  - `tests_local/seed_test_data.py`;
  - `tests_local/reset_test_db.py`;
  - `tests_local/test_search_logic.py`;
  - `tests_local/run_local.py`;
  - `tests_local/README.md`.

## Важные ограничения

- PostgreSQL обязателен. SQLite fallback не реализован.
- Если БД недоступна или миграция не применена, приложение возвращает понятную ошибку подключения и не падает обратно на live scraping.
- Seed и локальные SQL-тесты не делают запросов к Rezka/IMDb.
- `query_hash` строится из фильтров поиска и сортировки, но не из `limit`, чтобы одинаковый запрос с разными лимитами использовал одну историю показов.

## Как запустить локально

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://hdrezka_user:password@localhost:5432/hdrezka_filter"
psql $env:DATABASE_URL -f migrations/001_init.sql
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/seed_test_data.py
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" main.py
```

Открыть:

```text
http://127.0.0.1:8000/
```

## Как остановить сервер

- Кнопкой `Остановить сервер` в интерфейсе.
- Через PowerShell:

```powershell
.\stop_server.ps1
```

- Вручную по PID:

```powershell
netstat -ano | Select-String ':8000'
Stop-Process -Id <PID>
```

## Проверки

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m py_compile main.py app/**/*.py tests_local/*.py
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tests_local/test_search_logic.py
```

Второй тест требует поднятый PostgreSQL, примененную миграцию и установленный `psycopg[binary]`.

## Следующие этапы

1. Добавить crawler, который аккуратно наполняет PostgreSQL из Rezka/IMDb с лимитами и паузами.
2. Добавить кэширование/логирование ошибок crawler-а через `crawl_log`.
3. После стабильного DB MVP перейти на FastAPI.
4. После этого упаковать в Docker.
5. Затем переносить на VPS и закрывать доступ через Tailscale.
