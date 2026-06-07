# HdRezka Search: текущий статус

## Общий статус

Проект находится в рабочем тестовом MVP-состоянии:

- backend переведен на FastAPI;
- данные хранятся в PostgreSQL;
- обычный поиск работает только по локальной БД и не дергает Rezka/IMDb;
- БД наполняется вручную через кнопку `Загрузить еще` или CLI crawler;
- Dockerfile и Docker Compose добавлены;
- есть инструкция для запуска через Tailscale на локальной машине или VPS;
- пассивного фонового crawler-а пока нет.

## Что работает

- Web UI:
  - два пользователя задаются через `APP_USERS`;
  - переключение карточки/текст;
  - темная тема через switch;
  - сортировка применятся без повторного нажатия `Искать`;
  - кнопка `Загрузить еще`;
  - статус crawler-а показывает каталог, текущую ссылку, счетчики и ошибки.
- API:
  - `GET /`;
  - `GET /api/users`;
  - `GET /api/search`;
  - `POST /api/movie-state`;
  - `POST /api/crawl`;
  - `GET /api/crawl-progress`.
- Поиск:
  - фильтр по тексту;
  - фильтр по жанрам и странам;
  - ban жанров и стран;
  - IMDb min/max;
  - тип контента;
  - сортировка по IMDb, названию и random;
  - исключение уже показанных результатов через `shown_items`;
  - пользовательские состояния `seen`, `hidden`, `favorite`, `watchlist`.
- Crawler:
  - CLI: `python -m app.crawler run`;
  - источники CLI: `new`, `popular`, `genres`, `best`;
  - UI `auto` идет в жанровый каталог, если жанр распознан;
  - UI `Популярное по фильтрам` идет в `/{section}/best/{genre}/`, если жанр распознан;
  - страны не добавляются в URL, а применяются только как фильтр после чтения фильма;
  - типы мапятся в разделы Rezka:
    - `film` -> `/films/`;
    - `series` -> `/series/`;
    - `cartoon` -> `/cartoons/`;
    - `anime` -> `/animation/`;
  - crawler пропускает фильмы, которые уже есть в БД по `rezka_url`;
  - crawler продолжает идти по страницам до лимита сохраненных фильмов или лимита страниц;
  - текущие фильтры genre/country/ban/content type/IMDb применяются перед сохранением;
  - сохраняются ссылки на фильм и постер, сами изображения не скачиваются;
  - IMDb-рейтинг и `imdb_id` парсятся со страницы Rezka, если доступны;
  - ошибки пишутся в `crawl_log`;
  - статус каталога пишется в `catalog_crawl_state`.
- Cookies:
  - `REZKA_COOKIE` можно задать в `.env`;
  - `REZKA_COOKIE_FILE` имеет приоритет над `REZKA_COOKIE`;
  - `python -m app.cookie_refresher refresh` обновляет cookies через Playwright/headless;
  - scheduler cookie-refresh может запускаться вместе с FastAPI;
  - cookie-refresh не наполняет БД.
- Telegram alerts:
  - токен и chat id читаются из `.env`;
  - алерты отправляются при ошибках FastAPI, crawler-а и cookie-refresh;
  - если env-переменные пустые, модуль молча отключен.
- Docker:
  - `Dockerfile` собирает app-образ с Playwright Chromium;
  - `docker-compose.yml` поднимает `db`, `init-db`, `app`;
  - `init-db` применяет миграцию, чистит runtime-таблицы и создает пользователей из `APP_USERS`.

## Важные ограничения

- PostgreSQL обязателен, SQLite fallback нет.
- Обычный `/api/search` не делает live-запросов к Rezka или IMDb.
- Пассивного фонового наполнения БД нет: только кнопка `Загрузить еще` и CLI.
- Если Rezka возвращает `403`, нужны актуальные browser cookies/User-Agent/Accept-Language.
- Playwright cookie-refresh может не помочь, если Rezka требует интерактивную проверку в обычном браузере.
- UI-дозагрузка ограничивается `CRAWLER_LOAD_MORE_PAGE_LIMIT` и `CRAWLER_LOAD_MORE_ITEM_LIMIT`.
- Узкие фильтры могут сохранить меньше фильмов, чем лимит, если за разрешенное число страниц подходящих кандидатов мало.
- `Не повторять показанные` может дать пустую выдачу после предыдущего поиска, даже если фильмы есть в БД.

## Текущий запуск через Docker Compose

```bash
cp .env.example .env
mkdir -p runtime

docker compose up -d db
docker compose run --rm init-db
docker compose up -d --build app
```

Открыть локально:

```text
http://127.0.0.1:8000/
```

Открыть через Tailscale:

```text
http://TAILSCALE_IP:8000/
```

Полезные команды:

```bash
docker compose ps
docker compose logs -f app
docker compose restart app
docker compose up -d --build app
```

## Проверки

```bash
.venv/bin/python -m py_compile main.py app/*.py app/**/*.py tests_local/*.py
.venv/bin/python tests_local/test_search_logic.py
```

`test_search_logic.py` требует поднятую PostgreSQL и примененную миграцию.

## Следующие этапы

1. Протестировать crawler на большем наборе жанров/типов, особенно `animation` и `cartoons`.
2. Подобрать production-лимиты для UI-дозагрузки.
3. Добавить retry/backoff для Rezka metadata-запросов.
4. Определиться, нужен ли настоящий фоновый scheduled crawler.
5. После стабильного теста на локальной машине перенести на VPS через Docker Compose + Tailscale.
