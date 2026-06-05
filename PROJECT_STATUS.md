# HdRezka Filter: статус FastAPI + Crawler MVP

## Текущий вектор

Проект остается локальным DB-first MVP: обычный пользовательский поиск не дергает Rezka или IMDb, а читает PostgreSQL-таблицу `movies`. Наполнение БД вынесено в отдельный crawler CLI. Web-слой переведен с `http.server` на FastAPI.

Docker Compose, VPS и Tailscale пока не трогаются. Для локального теста можно поднимать PostgreSQL обычным Docker-контейнером.

## Что реализовано

- `.env.example` с настройками подключения к БД и лимитами crawler-а.
- PostgreSQL-слой:
  - `app/database.py` с `fetch_one`, `fetch_all`, `execute`, `execute_many`;
  - `migrations/001_init.sql` со схемой БД и seed-пользователями `test1`/`test2`;
  - `DATABASE_URL`, `HDREZKA_DEBUG`, crawler-лимиты и IMDb-лимиты читаются из env.
- FastAPI web/API:
  - `GET /`;
  - `GET /api/users`;
  - `GET /api/search`;
  - `POST /api/movie-state`;
  - `POST /api/crawl`;
  - static files через `/static/*`.
- Поиск по SQL:
  - include жанров/стран работает как `AND`;
  - ban жанров/стран работает как `OR` exclusion через `NOT EXISTS`;
  - есть фильтры IMDb min/max, `content_type`, сортировка;
  - `seen` и `hidden` исключаются только для выбранного пользователя;
  - `favorite` и `watchlist` не исключают фильм из поиска;
  - повторный поиск может исключать уже показанные фильмы по `user_id + query_hash`;
  - `query_hash` не включает `limit`;
  - сортировка `random` делает случайную подборку после применения всех фильтров.
- Crawler CLI:
  - запуск: `python -m app.crawler run`;
  - по умолчанию обходит новинки Rezka `/new/` и `/new/page/N/`;
  - опционально обходит жанры фильмов Rezka через `--source genres`;
  - UI-дозагрузка выбирает источник по текущим фильтрам: жанр ведет в `/films/{slug}/`, без жанра используется `/new/`;
  - перед сохранением применяет текущие include/ban фильтры жанров/стран и `content_type`;
  - лимит UI-дозагрузки считается по сохраненным подходящим фильмам, но при узких фильтрах результат может быть меньше лимита после просмотра разрешенного числа страниц;
  - базовый домен Rezka читается из `REZKA_BASE_URL`;
  - сохраняет ссылки на фильмы и ссылки на постеры, сами изображения не скачивает;
  - IMDb-рейтинг и `imdb_id` парсятся со страницы Rezka, если доступны;
  - ограничивается `CRAWLER_PAGE_LIMIT`, `CRAWLER_ITEM_LIMIT`, `CRAWLER_SLEEP_SECONDS`;
  - читает metadata страницы фильма;
  - по умолчанию обогащает IMDb-рейтингом с `CRAWLER_IMDB_ITEM_LIMIT`;
  - пишет фильмы, жанры, страны в PostgreSQL;
  - пишет статус в `catalog_crawl_state` и события/ошибки в `crawl_log`.
- Frontend MVP:
  - выбор пользователя `test1`/`test2`;
  - поиск отправляет `user_id`;
  - карточки получают `movie_id`;
  - кнопки `Уже смотрел`, `Скрыть`, `В избранное`, `Хочу посмотреть`;
  - кнопка `Загрузить еще` для небольшой дозагрузки базы crawler-ом;
  - переключение `Карточки`/`Текст` перерисовывает текущую выдачу без повторного поиска;
  - смена сортировки автоматически перезапускает последний поиск;
  - после `Уже смотрел`/`Скрыть` карточка убирается из текущей выдачи локально.
- Локальные инструменты:
  - `tests_local/seed_test_data.py`;
  - `tests_local/reset_test_db.py`;
  - `tests_local/test_search_logic.py`;
  - `tests_local/run_local.py`.

## Важные ограничения

- PostgreSQL обязателен. SQLite fallback не реализован.
- Если БД недоступна или миграция не применена, API возвращает понятную ошибку подключения и не падает обратно на live scraping.
- Обычный `/api/search` не делает запросов к Rezka/IMDb.
- Crawler делает сетевые запросы к Rezka и IMDb, поэтому для smoke-тестов нужно ставить маленькие лимиты.
- Если Rezka возвращает `403 Forbidden`, нужно обновить локальные `REZKA_USER_AGENT`, `REZKA_ACCEPT_LANGUAGE` и `REZKA_COOKIE` в `.env` через браузерный DevTools -> Network -> Copy as cURL.
- Остановка FastAPI-сервера выполняется через `Ctrl+C` в терминале.

## Как запустить локально

```bash
cd "/home/agh/Desktop/hdrezka test /hdrezka_search"

docker run --name hdrezka-postgres \
  -e POSTGRES_USER=hdrezka_user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=hdrezka_filter \
  -p 5432:5432 \
  -d postgres:16

cp .env.example .env

python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

export DATABASE_URL="postgresql://hdrezka_user:password@localhost:5432/hdrezka_filter"
psql "$DATABASE_URL" -f migrations/001_init.sql
```

Для crawler-а с Rezka в `.env` должны быть актуальные браузерные значения:

```env
REZKA_BASE_URL=https://rezka.ag/
REZKA_USER_AGENT=...
REZKA_ACCEPT_LANGUAGE=...
REZKA_COOKIE=...
```

Для тестовых локальных данных без сети:

```bash
.venv/bin/python tests_local/seed_test_data.py
```

Для реального наполнения crawler-ом:

```bash
.venv/bin/python -m app.crawler run
```

Для быстрого crawler smoke-run:

```bash
CRAWLER_PAGE_LIMIT=1 CRAWLER_ITEM_LIMIT=5 CRAWLER_IMDB_ITEM_LIMIT=2 .venv/bin/python -m app.crawler run
```

Обход жанров вместо новинок:

```bash
.venv/bin/python -m app.crawler run --source genres
```

Запуск web:

```bash
.venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

Открыть:

```text
http://127.0.0.1:8000/
```

## Проверки

```bash
.venv/bin/python -m py_compile main.py app/*.py app/**/*.py tests_local/*.py
.venv/bin/python tests_local/test_search_logic.py
```

Второй тест требует поднятый PostgreSQL, примененную миграцию и установленный `psycopg[binary]`.

FastAPI smoke-test:

```bash
curl http://127.0.0.1:8000/api/users
curl "http://127.0.0.1:8000/api/search?user_id=1&query=фантастика&limit=2&exclude_seen=0"
```

## Следующие этапы

1. Стабилизировать crawler на реальном объеме данных и уточнить парсинг content type.
2. Добавить retry/backoff и более подробную статистику crawler-а.
3. После стабильного FastAPI + DB + crawler MVP упаковать в Docker Compose.
4. Затем переносить на VPS и закрывать доступ через Tailscale.
