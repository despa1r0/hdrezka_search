# HdRezka DB Filter

Локальная страница поиска по собственной PostgreSQL-базе фильмов. Обычный поиск не делает live-запросы к Rezka или IMDb: данные сначала должны быть загружены в БД.

## Возможности

- пользователи задаются через `APP_USERS`;
- отдельные состояния фильмов для каждого пользователя: `seen`, `hidden`, `favorite`, `watchlist`;
- история показанных результатов по `user_id + query_hash`;
- фильтры жанров и стран на включение;
- бан-листы жанров и стран;
- фильтр IMDb min/max;
- сортировка IMDb от высокой или от низкой;
- случайная подборка с сохранением всех фильтров;
- режим карточек и текстовый режим;
- темная тема;
- дозагрузка новинок, популярных или жанровых каталогов кнопкой `Загрузить еще`;
- автообновление Rezka cookies через Playwright/headless;
- Telegram-алерты для падений crawler-а, FastAPI и cookie-refresh;
- Dockerfile и Docker Compose для запуска web-приложения с PostgreSQL;
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
Rezka, например `/films/detective/`, `/series/detective/`,
`/cartoons/detective/` или `/animation/detective/`, и дополнительно применяет текущие
include/ban фильтры перед сохранением. Если жанр не выбран, используется
источник новинок `/new/`. В поле `Источник дозагрузки` можно явно выбрать
`Новинки` или `Популярное по фильтрам`. Если для текущего запроса распознан
жанр, популярное ходит в каталог `best`, например:

```text
https://rezka.ag/films/best/detective/
https://rezka.ag/films/best/detective/page/2/
```

Для `Тип = Аниме` используется раздел `/animation/`, например
`/animation/best/horror/`; для мультфильмов `/cartoons/`, для сериалов
`/series/`.

Страны не добавляются в URL и применяются только как фильтр после чтения
страницы фильма. Если жанр не распознан, используется общий popular:

```text
https://rezka.ag/new/?filter=popular
https://rezka.ag/new/page/2/?filter=popular
```

По умолчанию один клик дозагрузки ограничен:

```env
CRAWLER_LOAD_MORE_PAGE_LIMIT=3
CRAWLER_LOAD_MORE_ITEM_LIMIT=30
CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT=0
CRAWLER_LOAD_MORE_SLEEP_SECONDS=0
```

Пассивного фонового наполнения БД сейчас нет: база наполняется только вручную
через кнопку `Загрузить еще` или CLI `python -m app.crawler run`. Scheduler
cookie-refresh обновляет только cookies для Rezka, но не запускает crawler.

`CRAWLER_LOAD_MORE_ITEM_LIMIT` означает целевое количество сохраненных подходящих
фильмов, а не просмотренных карточек. Crawler применяет текущие genre/country,
ban-фильтры, content type и IMDb-диапазон перед сохранением. При узких фильтрах, например
`Детективы + Великобритания`, crawler может просмотреть много кандидатов,
пропустить неподходящие страны и сохранить меньше лимита, если за
`CRAWLER_LOAD_MORE_PAGE_LIMIT` страниц подходящих фильмов мало.

UI-дозагрузка хранит resume-прогресс отдельно для каждого набора фильтров и
источника. Поэтому разные запросы не сбивают друг другу `last_page`, но повторный
клик с теми же фильтрами продолжает идти глубже по тому же каталогу.

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

Популярное и best-каталоги доступны отдельно:

```bash
.venv/bin/python -m app.crawler run --source popular
.venv/bin/python -m app.crawler run --source best --best-slugs detective
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

## Env notes

`HDREZKA_DEBUG=0` выключает подробный debug-вывод. Если поставить `1`, поиск
будет писать SQL/debug параметры в stdout или `docker compose logs app`.

`REZKA_COOKIE_REFRESH_WRITE_ENV=0` означает, что Playwright cookie-refresh не
перезаписывает `.env`; новые cookies пишутся только в `REZKA_COOKIE_FILE`,
например `runtime/rezka_cookie.txt`. Если поставить `1`, refresh дополнительно
заменит строку `REZKA_COOKIE=` в локальном `.env`.

`REZKA_FETCH_MODE=requests` оставляет старый HTTP-клиент для Rezka. Если Rezka
отдает `403` обычным HTTP-запросам, можно включить браузерный fetch:

```env
REZKA_FETCH_MODE=playwright
REZKA_PLAYWRIGHT_BROWSER=firefox
REZKA_PLAYWRIGHT_HEADLESS=1
REZKA_PLAYWRIGHT_PROFILE_DIR=runtime/rezka_browser_profile
```

Опциональный proxy только для браузерных Rezka-запросов:

```env
REZKA_PLAYWRIGHT_PROXY=http://user:password@host:port
```

Crawler переиспользует один persistent browser profile в течение запуска и
между запусками. Если Playwright на VPS все равно получает `403`, проблема
обычно в исходящем IP/датацентре, а не в cookies.

`CRAWLER_SOURCE=new` задает дефолтный источник CLI crawler-а. Значения:
`new` ходит по `/new/`, `popular` по `/new/?filter=popular`, `best` по
`/{section}/best/{slug}/`, `genres` по жанровым каталогам. В UI значение `auto`
выбирает жанровый каталог, если жанр распознан из запроса или фильтра; иначе
используется `new`. UI-источник `Популярное по фильтрам` выбирает `best`, если
есть распознанный жанр, иначе падает обратно на общий `popular`.

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

## Docker Compose local

Основной способ запуска: Docker Compose. Он поднимает PostgreSQL, web-app и
одноразовый init-сервис для чистой БД.

```bash
cp .env.example .env
mkdir -p runtime

docker compose up -d db
docker compose run --rm init-db
docker compose up -d --build app
```

Открыть:

```text
http://127.0.0.1:8000/
```

`init-db` применяет миграцию, удаляет тестовые фильмы/состояния/логи и создает
пользователей из `.env`:

```env
APP_USERS=user1:User 1,user2:User 2
```

Повторный запуск `init-db` очищает БД. Не запускай его, если хочешь сохранить
уже накрауленные фильмы.

Полезные команды:

```bash
docker compose logs -f app
docker compose logs -f db
docker compose restart app
docker compose down
docker compose up -d --build app
```

Разовая команда cookie-refresh внутри Compose:

```bash
docker compose run --rm app python -m app.cookie_refresher refresh
```

Разовый запуск crawler-а:

```bash
docker compose run --rm app python -m app.crawler run --source popular --page-limit 1 --item-limit 10
```

Разовый запуск crawler-а через Playwright без изменения `.env`:

```bash
docker compose run --rm -e REZKA_FETCH_MODE=playwright -e REZKA_PLAYWRIGHT_BROWSER=firefox app python -m app.crawler run --source new --page-limit 1 --item-limit 5
```

## VPS + Tailscale

Рекомендуемый вариант: Tailscale ставится на сам VPS, а Docker публикует
web-контейнер только на Tailscale IP. Так app доступен участникам tailnet, но
не торчит в публичный интернет.

На чистом Ubuntu/Debian VPS:

```bash
sudo apt update
sudo apt install -y git curl
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
```

Перезайди по SSH, чтобы группа `docker` применилась, затем поставь Tailscale:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4
```

Скопируй Tailscale IP. Дальше залей проект:

```bash
git clone https://github.com/despa1r0/hdrezka_search.git
cd hdrezka_search

cp .env.example .env
nano .env
```

В `.env` на VPS выставь. `APP_USERS` можно сразу заменить на новые имена:

```env
COMPOSE_PROJECT_NAME=hdrezka_search
POSTGRES_USER=hdrezka_user
POSTGRES_PASSWORD=replace_with_strong_password
POSTGRES_DB=hdrezka_filter
APP_BIND=TAILSCALE_IP_СЮДА
APP_PORT=8000
APP_USERS=client1:Client 1,client2:Client 2
DATABASE_URL=postgresql://hdrezka_user:replace_with_strong_password@db:5432/hdrezka_filter
REZKA_COOKIE_REFRESH_ENABLED=1
REZKA_COOKIE_REFRESH_HOUR=2
REZKA_COOKIE_REFRESH_MINUTE=0
TELEGRAM_ALERTS_ENABLED=1
TELEGRAM_BOT_TOKEN=replace_me
TELEGRAM_CHAT_ID=replace_me
```

`APP_BIND` важен: так Docker будет слушать только Tailscale-адрес VPS, а не
публичный интернет.

### Чистый старт без переноса БД

Только для пустой базы:

```bash
mkdir -p runtime
docker compose up -d db
docker compose run --rm init-db
docker compose up -d --build app
```

`init-db` удаляет фильмы/состояния. Не запускай эту команду, если переносишь
текущую базу.

### Перенос текущей БД

На старой машине сделай дамп:

```bash
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/hdrezka_filter_$(date +%Y%m%d_%H%M%S).dump
```

Скопируй дамп на VPS, например:

```bash
scp backups/hdrezka_filter_20260609_153444.dump user@VPS_IP:/opt/hdrezka_search/backups/
```

На VPS восстанови дамп вместо `init-db`:

```bash
cd /opt/hdrezka_search
mkdir -p runtime backups
docker compose up -d db
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backups/hdrezka_filter_20260609_153444.dump
docker compose up -d --build app
```

Если нужно переименовать существующих пользователей и сохранить их `seen`,
`favorite`, `shown_items`, выставь новый `APP_USERS` в `.env` и запусти:

```bash
docker compose run --rm app python -m app.admin rename-existing-users
docker compose restart app
```

Команда сопоставляет пользователей по текущему `id` и порядку в `APP_USERS`.
Количество пользователей в базе и в `APP_USERS` должно совпадать.

Открыть с телефона, подключенного к тому же Tailnet:

```text
http://TAILSCALE_IP_ТВОЕГО_VPS:8000/
```

Если включен `ufw`, разреши порт только на Tailscale-интерфейсе:

```bash
sudo ufw allow in on tailscale0 to any port 8000 proto tcp
```

Обновление после нового push:

```bash
git pull
docker compose up -d --build app
```

### Фоновые задачи

Пассивного фонового заполнения фильмов нет: crawler запускается кнопкой
`Загрузить еще` в UI или CLI-командой `python -m app.crawler run`.

Автообновление cookies через Playwright работает только если
`REZKA_COOKIE_REFRESH_ENABLED=1`. При старте FastAPI запускается daemon thread,
который обновляет cookies раз в день в `REZKA_COOKIE_REFRESH_HOUR:MINUTE` и
пишет их в `REZKA_COOKIE_FILE`, обычно `runtime/rezka_cookie.txt`.

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
