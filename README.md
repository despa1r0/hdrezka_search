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
- случайная подборка с сохранением всех фильтров;
- режим карточек и текстовый режим;
- дозагрузка новинок, популярных или жанровых каталогов кнопкой `Загрузить еще`;
- автообновление Rezka cookies через Playwright/headless;
- Telegram-алерты для падений crawler-а, FastAPI и cookie-refresh;
- Dockerfile для запуска web-приложения в контейнере;
- локальные seed/reset/test скрипты без сетевых запросов.

## Установка

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## База

```bash
docker run --name hdrezka-postgres \
  -e POSTGRES_USER=hdrezka_user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=hdrezka_filter \
  -p 5432:5432 \
  -d postgres:16

cp .env.example .env
export DATABASE_URL="postgresql://hdrezka_user:password@localhost:5432/hdrezka_filter"
psql "$DATABASE_URL" -f migrations/001_init.sql
```

Если Rezka возвращает `403`, открой `https://rezka.ag/new/` в браузере,
сделай DevTools -> Network -> Copy as cURL и перенеси актуальные значения
`User-Agent`, `Accept-Language` и `Cookie` в `.env`:

```env
REZKA_USER_AGENT=...
REZKA_ACCEPT_LANGUAGE=...
REZKA_COOKIE=...
```

Cookie можно обновить через Playwright/headless:

```bash
.venv/bin/python -m playwright install chromium
.venv/bin/python -m app.cookie_refresher refresh
```

По умолчанию cookie пишется в `runtime/rezka_cookie.txt`, а приложение читает
сначала этот файл, затем `REZKA_COOKIE` из `.env`. Для ежедневного обновления
в 02:00 при старте FastAPI:

```env
REZKA_COOKIE_REFRESH_ENABLED=1
REZKA_COOKIE_REFRESH_HOUR=2
REZKA_COOKIE_REFRESH_MINUTE=0
REZKA_COOKIE_FILE=runtime/rezka_cookie.txt
```

Если хочешь дополнительно перезаписывать строку `REZKA_COOKIE=` в локальном
`.env`, включи:

```env
REZKA_COOKIE_REFRESH_WRITE_ENV=1
```

Тестовые данные:

```bash
.venv/bin/python tests_local/seed_test_data.py
```

Сброс тестовых фильмов и пользовательских состояний:

```bash
.venv/bin/python tests_local/reset_test_db.py
```

## Crawler

```bash
.venv/bin/python -m app.crawler run
```

В интерфейсе кнопка `Загрузить еще` делает маленькую дозагрузку в БД.
Если в текущем поиске выбран жанр, crawler идет в соответствующий каталог
Rezka, например `/films/detective/`, и дополнительно применяет текущие
include/ban фильтры перед сохранением. Если жанр не выбран, используется
источник новинок `/new/`. В поле `Источник дозагрузки` можно явно выбрать
`Новинки` или `Популярное`; популярное ходит по:

```text
https://rezka.ag/new/?filter=popular
https://rezka.ag/new/page/2/?filter=popular
```

По умолчанию один клик дозагрузки ограничен:

```env
CRAWLER_LOAD_MORE_PAGE_LIMIT=3
CRAWLER_LOAD_MORE_ITEM_LIMIT=12
CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT=0
CRAWLER_LOAD_MORE_SLEEP_SECONDS=0
```

`CRAWLER_LOAD_MORE_ITEM_LIMIT` означает целевое количество сохраненных подходящих
фильмов, а не просмотренных карточек. При узких фильтрах, например
`Детективы + Великобритания`, crawler может просмотреть много кандидатов,
пропустить неподходящие страны и сохранить меньше лимита, если за
`CRAWLER_LOAD_MORE_PAGE_LIMIT` страниц подходящих фильмов мало.

Crawler сохраняет ссылки на фильмы и ссылки на постеры, но не скачивает сами изображения.
IMDb-рейтинг и `imdb_id` берутся со страницы Rezka, если они там указаны.

По умолчанию crawler ходит по новинкам:

```text
https://rezka.ag/new/
https://rezka.ag/new/page/2/
```

Обход жанров доступен отдельно:

```bash
.venv/bin/python -m app.crawler run --source genres
```

Популярное доступно отдельно:

```bash
.venv/bin/python -m app.crawler run --source popular
```

Быстрый smoke-run:

```bash
CRAWLER_PAGE_LIMIT=1 CRAWLER_ITEM_LIMIT=5 CRAWLER_IMDB_ITEM_LIMIT=2 .venv/bin/python -m app.crawler run
```

## Запуск web

```bash
.venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

Открыть:

```text
http://127.0.0.1:8000/
```

Debug:

```bash
HDREZKA_DEBUG=1 .venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

## Telegram alerts

Создай Telegram-бота через BotFather, возьми token и chat id, затем добавь в
`.env`:

```env
TELEGRAM_ALERTS_ENABLED=1
TELEGRAM_BOT_TOKEN=123456:replace_me
TELEGRAM_CHAT_ID=123456789
```

Если эти значения пустые или `TELEGRAM_ALERTS_ENABLED=0`, приложение просто
не отправляет алерты.

## Docker

Собрать образ:

```bash
docker build -t hdrezka-search .
```

Если PostgreSQL уже запущен как локальный контейнер `hdrezka-postgres` с
портом `5432:5432`, самый простой Linux-вариант:

```bash
docker run --rm --name hdrezka-app \
  --network host \
  --env-file .env \
  -e DATABASE_URL=postgresql://hdrezka_user:password@127.0.0.1:5432/hdrezka_filter \
  -v "$PWD/runtime:/app/runtime" \
  hdrezka-search
```

Открыть:

```text
http://127.0.0.1:8000/
```

Вариант без host-network, через отдельную Docker-сеть:

```bash
docker network create hdrezka-net
docker network connect hdrezka-net hdrezka-postgres

docker run --rm --name hdrezka-app \
  --network hdrezka-net \
  --env-file .env \
  -e DATABASE_URL=postgresql://hdrezka_user:password@hdrezka-postgres:5432/hdrezka_filter \
  -p 8000:8000 \
  -v "$PWD/runtime:/app/runtime" \
  hdrezka-search
```

Разовая команда cookie-refresh внутри образа:

```bash
docker run --rm \
  --network host \
  --env-file .env \
  -v "$PWD/runtime:/app/runtime" \
  hdrezka-search \
  python -m app.cookie_refresher refresh
```

Разовый запуск crawler-а из образа:

```bash
docker run --rm \
  --network host \
  --env-file .env \
  -e DATABASE_URL=postgresql://hdrezka_user:password@127.0.0.1:5432/hdrezka_filter \
  -v "$PWD/runtime:/app/runtime" \
  hdrezka-search \
  python -m app.crawler run --source popular --page-limit 1 --item-limit 10
```

## Остановка сервера

Остановить `uvicorn` в терминале через `Ctrl+C`.

## Проверки

```bash
.venv/bin/python -m py_compile main.py app/*.py app/**/*.py tests_local/*.py
.venv/bin/python tests_local/test_search_logic.py
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
