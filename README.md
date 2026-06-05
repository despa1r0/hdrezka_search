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
- дозагрузка новинок в БД кнопкой `Загрузить еще`;
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
источник новинок `/new/`.

По умолчанию один клик дозагрузки ограничен:

```env
CRAWLER_LOAD_MORE_PAGE_LIMIT=1
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
