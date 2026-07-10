# HdRezka Search: текущий статус

## Общий статус

Проект находится в рабочем MVP-состоянии и уже перешел к DevOps-этапу.

Что есть сейчас:

- backend на FastAPI;
- PostgreSQL как обязательная база данных;
- поиск работает по локальной БД и не делает live-запросов к Rezka/IMDb;
- БД наполняется через кнопку `Загрузить еще`, CLI crawler или опциональный passive crawler;
- Dockerfile и локальный Docker Compose добавлены;
- production Compose добавлен отдельно в `docker-compose.prod.yml`;
- CI добавлен в GitHub Actions;
- публикация Docker image в GitHub Container Registry добавлена;
- CD по SSH на VPS добавлен: workflow синхронизирует infra-файлы, проверяет candidate-контейнер и обновляет app image;
- автоматические PostgreSQL backups добавлены через systemd timer;
- Grafana + Loki + Promtail добавлены для централизованных Docker logs;
- Telegram alerts есть для ошибок FastAPI/crawler/cookie-refresh.

## Что работает

- Web UI:
  - пользователи задаются через `APP_USERS`;
  - режим карточек и текстовый режим;
  - темная тема;
  - сортировка применяется без повторного нажатия `Искать`;
  - кнопка `Загрузить еще`;
  - статус crawler-а показывает каталог, текущую ссылку, счетчики и ошибки.
- API:
  - `GET /`;
  - `GET /healthz`;
  - `GET /readyz`;
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
- Passive crawler:
  - включается через `PASSIVE_CRAWLER_ENABLED=1`;
  - запускается вместе с FastAPI;
  - обходит `new`, `popular`, жанровые и best-каталоги;
  - хранит отдельный resume-прогресс в `catalog_crawl_state`;
  - по умолчанию выключен.
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
  - `Dockerfile` собирает app-образ с Playwright Chromium/Firefox;
  - `docker-compose.yml` поднимает `db`, `init-db`, `app`;
  - `docker-compose.prod.yml` использует image из GHCR, Gluetun proxy, healthchecks и candidate-контейнер для деплоя;
  - `docker-compose.observability.yml` поднимает `loki`, `promtail`, `grafana`;
  - `init-db` применяет миграцию, чистит runtime-таблицы и создает пользователей из `APP_USERS`.
- CI/CD:
  - CI запускается на `pull_request`, `push` в `master` и вручную;
  - CI компилирует Python-код, запускает health endpoint tests и проверяет Docker build;
  - publish job пушит image в `ghcr.io/despa1r0/hdrezka_search`;
  - deploy job запускается только при `vars.CD_ENABLED == 'true'`;
  - deploy job синхронизирует на VPS `docker-compose.prod.yml`, `docker-compose.observability.yml`, `scripts/` и `ops/`;
  - deploy job запускает immutable deploy по Git SHA через candidate-контейнер и rollback.
- Backups:
  - `scripts/backup-db.sh` делает `pg_dump -Fc`;
  - дамп проверяется через `pg_restore --list`;
  - создается `.sha256`;
  - retention по умолчанию 14 дней;
  - systemd timer запускает backup ежедневно.
- Observability:
  - Loki хранит Docker logs с retention 7 дней;
  - Promtail собирает Docker JSON logs через Docker socket и `/var/lib/docker/containers`;
  - Grafana автоматически получает Loki datasource через provisioning.

## Важные ограничения

- PostgreSQL обязателен, SQLite fallback нет.
- Обычный `/api/search` не делает live-запросов к Rezka или IMDb.
- Passive crawler выключен по умолчанию, пока его явно не включили в `.env`.
- Если Rezka возвращает `403`, нужны актуальные browser cookies/User-Agent/Accept-Language или браузерный fetch через Playwright/proxy.
- Playwright cookie-refresh может не помочь, если Rezka требует интерактивную проверку в обычном браузере.
- UI-дозагрузка ограничивается `CRAWLER_LOAD_MORE_PAGE_LIMIT` и `CRAWLER_LOAD_MORE_ITEM_LIMIT`.
- Узкие фильтры могут сохранить меньше фильмов, чем лимит, если за разрешенное число страниц подходящих кандидатов мало.
- `Не повторять показанные` может дать пустую выдачу после предыдущего поиска, даже если фильмы есть в БД.
- CD ожидает, что на VPS уже есть `/opt/hdrezka_search`, `.env`, Docker и доступ к GHCR image.
- CD не перезаписывает VPS `.env`, `runtime/` и `backups/`.
- Grafana/Loki дают централизованные логи, но метрики CPU/RAM/disk/container пока не добавлены.
- Dashboards и alerts поверх Loki пока не оформлены.

## Текущее DevOps-состояние

Репозиторий:

- ветка: `master`;
- remote сейчас может быть HTTPS или SSH в зависимости от локальной настройки;
- для удобного push лучше использовать SSH remote: `git@github.com:despa1r0/hdrezka_search.git`.

GitHub Actions:

- `.github/workflows/ci.yml` уже содержит jobs `test`, `publish`, `deploy`;
- `deploy` включается через `CD_ENABLED=true`;
- deploy использует secrets:
  - `VPS_SSH_PRIVATE_KEY`;
  - `VPS_KNOWN_HOSTS`;
  - `VPS_HOST`;
  - `VPS_PORT`;
  - `VPS_USER`.

VPS:

- production directory ожидается в `/opt/hdrezka_search`;
- production compose файл: `/opt/hdrezka_search/docker-compose.prod.yml`;
- observability compose файл: `/opt/hdrezka_search/docker-compose.observability.yml`;
- production env файл: `/opt/hdrezka_search/.env`;
- app container: `hdrezka-app`;
- db container: `hdrezka-postgres`;
- Gluetun container: `hdrezka-gluetun`.
- observability containers: `hdrezka-loki`, `hdrezka-promtail`, `hdrezka-grafana`.

## Лучший порядок дальнейших работ

1. Подтвердить текущий CD после нового push.
   - Убедиться, что `test`, `publish`, `deploy` проходят.
   - Проверить, что image tag у `hdrezka-app` совпадает с Git SHA.
   - Проверить `/readyz`.

2. Поднять Grafana/Loki/Promtail на VPS.
   - Добавить в VPS `.env` `OBS_BIND`, `GRAFANA_PORT`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`, `LOKI_PORT`.
   - Запустить `docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml up -d loki promtail grafana`.
   - Открыть Grafana через Tailscale и проверить Loki datasource.
   - Проверить LogQL-запросы `{container="hdrezka-app"}` и `{service="app"}`.

3. Добавить dashboards/alerts поверх Loki.
   - Dashboard по app logs.
   - Dashboard по crawler errors.
   - Dashboard по deploy/backup logs.
   - Alerts: app unhealthy, db unhealthy, backup failed, много crawler errors.

4. Добавить метрики, если нужны.
   - Prometheus.
   - cAdvisor.
   - node-exporter.
   - Grafana dashboards по CPU/RAM/disk/container.

5. После DevOps-базы вернуться к app-качеству.
   - Добавить retry/backoff для Rezka metadata-запросов.
   - Подобрать production-лимиты crawler-а.
   - Расширить тесты для crawler/search behavior.
   - Решить, включать ли passive crawler в production постоянно.

## Уже выполненный DevOps-порядок

1. Навести порядок в GitHub SSH для обычного push.
   - Создать или проверить локальный `ed25519` SSH key.
   - Добавить public key в GitHub account.
   - Переключить remote на `git@github.com:despa1r0/hdrezka_search.git`.
   - Проверить `ssh -T git@github.com` и `git push`.

2. Довести VPS до ожидаемой production-структуры.
   - Создать `/opt/hdrezka_search`.
   - Положить туда `docker-compose.prod.yml`, `scripts/deploy.sh`, `scripts/backup-db.sh`, `ops/systemd/*`.
   - Создать production `.env`.
   - Проверить Docker, Tailscale, Gluetun и доступ к GHCR.
   - Поднять `db`, восстановить или инициализировать БД, затем поднять `app`.

3. Включить и проверить CD.
   - Создать отдельный SSH key для GitHub Actions -> VPS.
   - Public key добавить в `/home/deploy/.ssh/authorized_keys` на VPS.
   - Private key добавить в GitHub secret `VPS_SSH_PRIVATE_KEY`.
   - Добавить `VPS_KNOWN_HOSTS`, `VPS_HOST`, `VPS_PORT`, `VPS_USER`.
   - Добавить repository variable `CD_ENABLED=true`.
   - Запустить workflow вручную через `workflow_dispatch`.
   - Проверить, что candidate container становится healthy и app обновляется.

4. Проверить backups.
   - Установить systemd unit/timer на VPS.
   - Запустить backup вручную.
   - Проверить наличие `.dump` и `.sha256`.
   - Один раз проверить restore на тестовой базе или отдельном контейнере.

5. Добавить централизованные логи в кодовую базу.
   - Добавить Loki.
   - Добавить Promtail для сбора Docker container logs.
   - Проставить labels для `app`, `db`, `gluetun`, `candidate`.
   - Ограничить retention логов.
   - Сделать Grafana datasource provisioning для Loki.

6. Добавить базовый monitoring в кодовую базу.
   - Добавить Grafana.
   - Добавить provisioning datasource для Loki.
   - Добавить compose overlay для observability.

7. Улучшить deploy infra-файлов.
   - CD синхронизирует `docker-compose.prod.yml`, `docker-compose.observability.yml`, `scripts/` и `ops/` перед deploy.
   - `.env`, `runtime/` и `backups/` не перезаписываются.

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
.venv/bin/python -m compileall -q app tests_local main.py
.venv/bin/python -m unittest tests_local.test_health_endpoints
.venv/bin/python tests_local/test_search_logic.py
```

`test_search_logic.py` требует поднятую PostgreSQL и примененную миграцию.
